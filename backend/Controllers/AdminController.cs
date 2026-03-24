using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using EbayHunter.API.Data;
using EbayHunter.API.DTOs;
using EbayHunter.API.Models;
using EbayHunter.API.Services;

namespace EbayHunter.API.Controllers;

[ApiController]
[Route("api/admin")]
[Authorize(Roles = "Admin,Developer")]
public class AdminController : ControllerBase
{
    private readonly AppDbContext _db;


    private const string DEV_ROLE = AuthService.DEV_ROLE;

    public AdminController(AppDbContext db) => _db = db;

    // ── List users — Developer accounts NEVER appear ──────────────────────────

    [HttpGet("users")]
    public async Task<IActionResult> GetUsers()
    {
        var users = await _db.Users
            .Where(u => u.Role != DEV_ROLE)          // ✅ EF Core can translate this
            .OrderByDescending(u => u.CreatedAt)
            .Select(u => new AdminUserView
            {
                Id          = u.Id,
                Email       = u.Email,
                Role        = u.Role,
                SearchLimit = u.Role == "Admin" ? -1 : u.SearchLimit,
                SearchUsed  = u.Role == "Admin" ? 0  : u.SearchUsed,
                Remaining   = u.Role == "Admin" ? -1 : Math.Max(0, u.SearchLimit - u.SearchUsed),
                CreatedAt   = u.CreatedAt,
            })
            .ToListAsync();

        return Ok(users);
    }

    // ── Create user ───────────────────────────────────────────────────────────

    [HttpPost("users")]
    public async Task<IActionResult> CreateUser([FromBody] AdminCreateUserRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
            return BadRequest(new { error = "Email and password are required." });

        if (request.Password.Length < 4)
            return BadRequest(new { error = "Password must be at least 4 characters." });

        var validRoles = new[] { "Free", "Basic", "Pro", "Admin" };
        var role = string.IsNullOrWhiteSpace(request.Role) ? "Free" : request.Role;
        if (!validRoles.Contains(role))
            return BadRequest(new { error = "Invalid role." });

        if (await _db.Users.AnyAsync(u => u.Email == request.Email.ToLower()))
            return Conflict(new { error = "Email already registered." });

        var user = new User
        {
            Email        = request.Email.ToLower().Trim(),
            PasswordHash = request.Password,
            Role         = role,
            SearchLimit  = AuthService.GetLimitForRole(role),
            SearchUsed   = 0,
        };

        _db.Users.Add(user);
        await _db.SaveChangesAsync();

        return Ok(new
        {
            message = $"User {user.Email} created with role {user.Role}.",
            user    = new AdminUserView
            {
                Id          = user.Id,
                Email       = user.Email,
                Role        = user.Role,
                SearchLimit = user.Role == "Admin" ? -1 : user.SearchLimit,
                SearchUsed  = 0,
                Remaining   = user.Role == "Admin" ? -1 : user.SearchLimit,
                CreatedAt   = user.CreatedAt,
            }
        });
    }

    // ── Update role ───────────────────────────────────────────────────────────

    [HttpPut("users/{id}/role")]
    public async Task<IActionResult> UpdateRole(Guid id, [FromBody] UpdateRoleRequest request)
    {
        var validRoles = new[] { "Free", "Basic", "Pro", "Admin" };
        if (!validRoles.Contains(request.Role))
            return BadRequest(new { error = "Invalid role." });

        var callerId = GetCallerId();
        if (callerId == id && request.Role != "Admin")
            return BadRequest(new { error = "You cannot change your own role." });

        var user = await _db.Users.FindAsync(id);
        if (user == null) return NotFound(new { error = "User not found." });

        // Cannot touch Developer accounts
        if (user.Role == DEV_ROLE)
            return NotFound(new { error = "User not found." });

        user.Role        = request.Role;
        user.SearchLimit = AuthService.GetLimitForRole(request.Role);
        user.SearchUsed  = 0;
        user.UpdatedAt   = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return Ok(new
        {
            message     = $"Role updated to {request.Role}",
            searchLimit = user.Role == "Admin" ? -1 : user.SearchLimit,
            remaining   = user.Role == "Admin" ? -1 : user.SearchLimit,
        });
    }

    // ── Top-up searches ───────────────────────────────────────────────────────

    [HttpPost("users/{id}/topup")]
    public async Task<IActionResult> TopUp(Guid id, [FromBody] TopUpRequest request)
    {
        if (request.Amount <= 0 || request.Amount > 100_000)
            return BadRequest(new { error = "Amount must be between 1 and 100,000." });

        var user = await _db.Users.FindAsync(id);
        if (user == null) return NotFound(new { error = "User not found." });

        if (user.Role == DEV_ROLE)
            return NotFound(new { error = "User not found." });

        if (user.Role == "Admin")
            return BadRequest(new { error = "Admin users have unlimited searches." });

        user.SearchLimit += request.Amount;
        user.UpdatedAt    = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return Ok(new
        {
            message     = $"Added {request.Amount} searches. New limit: {user.SearchLimit}.",
            searchLimit = user.SearchLimit,
            remaining   = Math.Max(0, user.SearchLimit - user.SearchUsed),
        });
    }

    // ── Delete user — Admin and Developer accounts cannot be deleted ──────────

    [HttpDelete("users/{id}")]
    public async Task<IActionResult> DeleteUser(Guid id)
    {
        var callerId = GetCallerId();
        if (callerId == id)
            return BadRequest(new { error = "You cannot delete your own account." });

        var user = await _db.Users.FindAsync(id);
        if (user == null) return NotFound(new { error = "User not found." });

        if (user.Role == "Admin" || user.Role == DEV_ROLE)
            return BadRequest(new { error = "Admin accounts cannot be deleted." });

        _db.Users.Remove(user);
        await _db.SaveChangesAsync();

        return Ok(new { message = "User deleted." });
    }

    // ── Stats — Developer accounts excluded from all counts ───────────────────

    [HttpGet("stats")]
    public async Task<IActionResult> GetStats()
    {
        var totalUsers    = await _db.Users
            .Where(u => u.Role != DEV_ROLE)          // ✅ EF Core can translate this
            .CountAsync();

        var totalSearches = await _db.SearchHistories
            .Where(s => s.User.Role != DEV_ROLE)     // ✅
            .CountAsync();

        var todaySearches = await _db.SearchHistories
            .Where(s => s.CreatedAt.Date == DateTime.UtcNow.Date
                     && s.User.Role != DEV_ROLE)     // ✅
            .CountAsync();

        var roleBreakdown = await _db.Users
            .Where(u => u.Role != DEV_ROLE)          // ✅
            .GroupBy(u => u.Role)
            .Select(g => new { Role = g.Key, Count = g.Count() })
            .ToListAsync();

        var recentSearches = await _db.SearchHistories
            .Where(s => s.User.Role != DEV_ROLE)     // ✅
            .OrderByDescending(s => s.CreatedAt)
            .Take(50)
            .Select(s => new
            {
                s.Id,
                s.Keyword,
                s.ResultCount,
                s.CreatedAt,
                UserEmail = s.User.Email,
                UserRole  = s.User.Role,
            })
            .ToListAsync();

        return Ok(new { totalUsers, totalSearches, todaySearches, roleBreakdown, recentSearches });
    }

    private Guid GetCallerId()
    {
        var claim = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return Guid.TryParse(claim, out var id) ? id : Guid.Empty;
    }
}