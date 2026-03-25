using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using EbayHunter.API.Data;
using EbayHunter.API.DTOs;
using EbayHunter.API.Models;
using EbayHunter.API.Services;

namespace EbayHunter.API.Controllers;

[ApiController]
[Route("api")]
[Authorize]
public class SearchController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly BotService _botService;

    public SearchController(AppDbContext db, BotService botService)
    {
        _db = db;
        _botService = botService;
    }

    /// <summary>Run eBay product search</summary>
    [HttpPost("search")]
    public async Task<IActionResult> Search([FromBody] SearchRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Keyword))
            return BadRequest(new { error = "Keyword is required." });

        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var user = await _db.Users.FindAsync(userId);
        if (user == null) return Unauthorized();

        // Auto-reset daily limit if day changed
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        if (user.LastResetDate < today)
        {
            user.SearchUsed = 0;
            user.LastResetDate = today;
        }

        // Check search limit
        int remaining = user.SearchLimit - user.SearchUsed;
        if (remaining <= 0)
        {
            return StatusCode(429, new
            {
                error = $"Daily search limit reached ({user.SearchLimit} for {user.Role} plan). Upgrade your plan for more searches.",
                searchesRemaining = 0
            });
        }

        // Increment search counter
        user.SearchUsed++;
        user.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        // Run the bot
        var products = await _botService.RunSearchAsync(request.Keyword);

        // Save to history
        var history = new SearchHistory
        {
            UserId = user.Id,
            Keyword = request.Keyword,
            Results = JsonSerializer.Serialize(products),
            ResultCount = products.Count
        };
        _db.SearchHistories.Add(history);
        await _db.SaveChangesAsync();

        return Ok(new SearchResponse
        {
            Success = true,
            Keyword = request.Keyword,
            Products = products,
            TotalFound = products.Count,
            SearchesRemaining = Math.Max(0, user.SearchLimit - user.SearchUsed)
        });
    }

    /// <summary>Get current user search limits</summary>
    [HttpGet("user/limits")]
    public async Task<IActionResult> GetLimits()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var user = await _db.Users.FindAsync(userId);
        if (user == null) return Unauthorized();

        return Ok(new UserLimitsResponse
        {
            Email = user.Email,
            Role = user.Role,
            SearchLimit = user.SearchLimit,
            SearchUsed = user.SearchUsed,
            Remaining = Math.Max(0, user.SearchLimit - user.SearchUsed),
            LastReset = user.LastResetDate.ToDateTime(TimeOnly.MinValue)
        });
    }

    /// <summary>Get current user search history</summary>
    [HttpGet("user/history")]
    public async Task<IActionResult> GetHistory()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var history = await _db.SearchHistories
            .Where(s => s.UserId == userId)
            .OrderByDescending(s => s.CreatedAt)
            .Take(50)
            .Select(s => new
            {
                s.Id,
                s.Keyword,
                s.Results,
                s.ResultCount,
                s.CreatedAt
            })
            .ToListAsync();

        return Ok(history);
    }

    private Guid? GetUserId()
    {
        var claim = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return Guid.TryParse(claim, out var id) ? id : null;
    }
}
