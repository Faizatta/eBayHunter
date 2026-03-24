using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using EbayHunter.API.Data;
using EbayHunter.API.DTOs;
using EbayHunter.API.Models;

namespace EbayHunter.API.Services;

public class AuthService
{
    private readonly AppDbContext   _db;
    private readonly IConfiguration _config;

    // ── Developer secret role ─────────────────────────────────────────────────
    // This role is completely invisible to Admin users — never shown in any list,
    // dropdown, history, or stats. Has unlimited searches like Admin.
    // Set via appsettings.json → "DeveloperAccess:SecretRole"
    public const string DEV_ROLE = "Developer";

    public AuthService(AppDbContext db, IConfiguration config)
    {
        _db     = db;
        _config = config;
    }

    public async Task<(bool Success, string Message, AuthResponse? Response)> RegisterAsync(RegisterRequest req)
    {
        if (await _db.Users.AnyAsync(u => u.Email == req.Email.ToLower()))
            return (false, "Email already registered.", null);

        if (string.IsNullOrWhiteSpace(req.Password) || req.Password.Length < 4)
            return (false, "Password must be at least 4 characters.", null);

        var user = new User
        {
            Email        = req.Email.ToLower().Trim(),
            PasswordHash = req.Password,   // plain text — no hashing
            Role         = "Free",
            SearchLimit  = GetLimitForRole("Free"),
            SearchUsed   = 0,
        };

        _db.Users.Add(user);
        await _db.SaveChangesAsync();

        return (true, "Registered successfully.", BuildAuthResponse(user, GenerateToken(user)));
    }

    public async Task<(bool Success, string Message, AuthResponse? Response)> LoginAsync(LoginRequest req)
    {
        var user = await _db.Users.FirstOrDefaultAsync(u => u.Email == req.Email.ToLower());

        // Plain text password check
        if (user == null || user.PasswordHash != req.Password)
            return (false, "Invalid email or password.", null);

        return (true, "Login successful.", BuildAuthResponse(user, GenerateToken(user)));
    }

    private string GenerateToken(User user)
    {
        var key    = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(
                         _config["Jwt:SecretKey"] ?? throw new InvalidOperationException("JWT key missing")));
        var creds  = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var expiry = DateTime.UtcNow.AddHours(double.Parse(_config["Jwt:ExpiryHours"] ?? "24"));

        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new Claim(ClaimTypes.Email, user.Email),
            new Claim(ClaimTypes.Role, user.Role),
        };

        return new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(
            issuer:             _config["Jwt:Issuer"],
            audience:           _config["Jwt:Audience"],
            claims:             claims,
            expires:            expiry,
            signingCredentials: creds
        ));
    }

    private static AuthResponse BuildAuthResponse(User user, string token)
    {
        bool unlimited = user.Role is "Admin" or DEV_ROLE;
        return new(
            token,
            user.Email,
            // Developer role appears as "Admin" to the frontend — completely hidden
            user.Role == DEV_ROLE ? "Admin" : user.Role,
            unlimited ? int.MaxValue : user.SearchLimit,
            user.SearchUsed,
            unlimited ? int.MaxValue : Math.Max(0, user.SearchLimit - user.SearchUsed)
        );
    }

    public static int GetLimitForRole(string role) => role switch
    {
        "Free"      => 5,
        "Basic"     => 50,
        "Pro"       => 200,
        "Admin"     => int.MaxValue,
        DEV_ROLE    => int.MaxValue,
        _           => 5
    };

    /// <summary>
    /// Returns true if this role should be completely hidden from Admin views.
    /// Developer accounts are invisible to all Admin panel queries.
    /// </summary>
    public static bool IsHiddenRole(string role) => role == DEV_ROLE;
}