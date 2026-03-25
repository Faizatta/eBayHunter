using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using EbayHunter.API.Data;
using EbayHunter.API.DTOs;
using EbayHunter.API.Services;

namespace EbayHunter.API.Controllers;

[ApiController]
[Route("api/admin")]
[Authorize(Roles = "Admin")]
public class AdminController : ControllerBase
{
    private readonly AppDbContext _db;

    public AdminController(AppDbContext db)
    {
        _db = db;
    }

    /// <summary>List all users</summary>
    [HttpGet("users")]
    public async Task<IActionResult> GetUsers()
    {
        var users = await _db.Users
            .OrderByDescending(u => u.CreatedAt)
            .Select(u => new AdminUserView
            {
                Id = u.Id,
                Email = u.Email,
                Role = u.Role,
                SearchLimit = u.SearchLimit,
                SearchUsed = u.SearchUsed,
                Remaining = Math.Max(0, u.SearchLimit - u.SearchUsed),
                CreatedAt = u.CreatedAt
            })
            .ToListAsync();

        return Ok(users);
    }

    /// <summary>Update user role</summary>
    [HttpPut("users/{id}/role")]
    public async Task<IActionResult> UpdateRole(Guid id, [FromBody] UpdateRoleRequest request)
    {
        var validRoles = new[] { "Free", "Basic", "Pro", "Admin" };
        if (!validRoles.Contains(request.Role))
            return BadRequest(new { error = "Invalid role. Valid: Free, Basic, Pro, Admin" });

        var user = await _db.Users.FindAsync(id);
        if (user == null) return NotFound(new { error = "User not found." });

        user.Role = request.Role;
        user.SearchLimit = AuthService.GetLimitForRole(request.Role);
        user.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return Ok(new { message = $"Role updated to {request.Role}", searchLimit = user.SearchLimit });
    }

    /// <summary>Reset user daily search limit</summary>
    [HttpPost("users/{id}/reset")]
    public async Task<IActionResult> ResetLimit(Guid id)
    {
        var user = await _db.Users.FindAsync(id);
        if (user == null) return NotFound(new { error = "User not found." });

        user.SearchUsed = 0;
        user.LastResetDate = DateOnly.FromDateTime(DateTime.UtcNow);
        user.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return Ok(new { message = "Search limit reset successfully." });
    }

    /// <summary>Get bot usage stats</summary>
    [HttpGet("stats")]
    public async Task<IActionResult> GetStats()
    {
        var totalUsers   = await _db.Users.CountAsync();
        var totalSearches = await _db.SearchHistories.CountAsync();
        var todaySearches = await _db.SearchHistories
            .Where(s => s.CreatedAt.Date == DateTime.UtcNow.Date)
            .CountAsync();

        var roleBreakdown = await _db.Users
            .GroupBy(u => u.Role)
            .Select(g => new { Role = g.Key, Count = g.Count() })
            .ToListAsync();

        var recentSearches = await _db.SearchHistories
            .OrderByDescending(s => s.CreatedAt)
            .Take(20)
            .Select(s => new
            {
                s.Id,
                s.Keyword,
                s.ResultCount,
                s.CreatedAt,
                UserEmail = s.User.Email
            })
            .ToListAsync();

        return Ok(new
        {
            totalUsers,
            totalSearches,
            todaySearches,
            roleBreakdown,
            recentSearches
        });
    }
}
