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
    private readonly AppDbContext _db;
    private readonly IConfiguration _config;

    public AuthService(AppDbContext db, IConfiguration config)
    {
        _db = db;
        _config = config;
    }

    public async Task<(bool Success, string Message, AuthResponse? Response)> RegisterAsync(RegisterRequest req)
    {
        if (await _db.Users.AnyAsync(u => u.Email == req.Email.ToLower()))
            return (false, "Email already registered.", null);

        if (string.IsNullOrWhiteSpace(req.Password) || req.Password.Length < 6)
            return (false, "Password must be at least 6 characters.", null);

        var user = new User
        {
            Email = req.Email.ToLower(),
            PasswordHash = BCrypt.Net.BCrypt.HashPassword(req.Password),
            Role = "Free",
            SearchLimit = 5,
            SearchUsed = 0
        };

        _db.Users.Add(user);
        await _db.SaveChangesAsync();

        var token = GenerateToken(user);
        return (true, "Registered successfully.", BuildAuthResponse(user, token));
    }

    public async Task<(bool Success, string Message, AuthResponse? Response)> LoginAsync(LoginRequest req)
    {
        var user = await _db.Users.FirstOrDefaultAsync(u => u.Email == req.Email.ToLower());
        if (user == null || !BCrypt.Net.BCrypt.Verify(req.Password, user.PasswordHash))
            return (false, "Invalid email or password.", null);

        // Auto-reset daily limits if day has changed
        await ResetDailyLimitIfNeededAsync(user);

        var token = GenerateToken(user);
        return (true, "Login successful.", BuildAuthResponse(user, token));
    }

    private string GenerateToken(User user)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(
            _config["Jwt:SecretKey"] ?? throw new InvalidOperationException("JWT key not configured")));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var expiry = DateTime.UtcNow.AddHours(double.Parse(_config["Jwt:ExpiryHours"] ?? "24"));

        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new Claim(ClaimTypes.Email, user.Email),
            new Claim(ClaimTypes.Role, user.Role)
        };

        var token = new JwtSecurityToken(
            issuer: _config["Jwt:Issuer"],
            audience: _config["Jwt:Audience"],
            claims: claims,
            expires: expiry,
            signingCredentials: creds
        );

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    private static AuthResponse BuildAuthResponse(User user, string token)
    {
        int remaining = user.SearchLimit - user.SearchUsed;
        return new AuthResponse(token, user.Email, user.Role, user.SearchLimit, user.SearchUsed, Math.Max(0, remaining));
    }

    private async Task ResetDailyLimitIfNeededAsync(User user)
    {
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        if (user.LastResetDate < today)
        {
            user.SearchUsed = 0;
            user.LastResetDate = today;
            user.UpdatedAt = DateTime.UtcNow;
            await _db.SaveChangesAsync();
        }
    }

    public static int GetLimitForRole(string role) => role switch
    {
        "Free"  => 5,
        "Basic" => 20,
        "Pro"   => 100,
        "Admin" => 999999,
        _       => 5
    };
}
