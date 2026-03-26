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
    private readonly BotService  _botService;

    public SearchController(AppDbContext db, BotService botService)
    {
        _db         = db;
        _botService = botService;
    }

    [HttpPost("search")]
    public async Task<IActionResult> Search([FromBody] SearchRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Keyword))
            return BadRequest(new { error = "Keyword is required." });

        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var user = await _db.Users.FindAsync(userId);
        if (user == null) return Unauthorized();

        bool unlimited = user.Role is "Admin" or AuthService.DEV_ROLE;

        if (!unlimited && user.SearchUsed >= user.SearchLimit)
            return StatusCode(429, new
            {
                error             = $"Search limit reached ({user.SearchLimit} searches for {user.Role} plan). Ask your admin to top up.",
                searchesRemaining = 0,
            });

        if (!unlimited)
        {
            user.SearchUsed++;
            user.UpdatedAt = DateTime.UtcNow;
            await _db.SaveChangesAsync();
        }

        var products = await _botService.RunSearchAsync(request.Keyword);

        _db.SearchHistories.Add(new SearchHistory
        {
            UserId      = user.Id,
            Keyword     = request.Keyword,
            Results     = JsonSerializer.Serialize(products),
            ResultCount = products.Count,
        });
        await _db.SaveChangesAsync();

        return Ok(new SearchResponse
        {
            Success  = true,
            Keyword  = request.Keyword,
            Products = products.Select(p => new {
                p.Title,
                p.Country,
                p.Currency,
                p.EbayPrice,
                EbayLowestPrice   = p.EbayPrice,
                p.AliexpressPrice,
                AliRating         = p.AliRating > 0 ? p.AliRating : 0.0,
                AliReviews        = p.Reviews,
                p.Profit,
                SoldPerWeek       = p.SoldLastWeek,
                TotalSoldMonth    = p.SoldLastWeek * 4,
                WeeklyConsistency = "",
                CompetitionLevel  = "medium",
                ActiveListings    = 0,
                p.FreeShipping,
                LocalShipping     = true,
                p.DeliveryDays,
                p.EbayUrl,
                p.AliexpressUrl,
            }).ToList(),
            TotalFound        = products.Count,
            SearchesRemaining = unlimited ? int.MaxValue : Math.Max(0, user.SearchLimit - user.SearchUsed),
        });
    }

    [HttpGet("user/limits")]
    public async Task<IActionResult> GetLimits()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var user = await _db.Users.FindAsync(userId);
        if (user == null) return Unauthorized();

        bool unlimited = user.Role is "Admin" or AuthService.DEV_ROLE;

        return Ok(new UserLimitsResponse
        {
            Email       = user.Email,
            Role        = user.Role == AuthService.DEV_ROLE ? "Admin" : user.Role,
            SearchLimit = unlimited ? int.MaxValue : user.SearchLimit,
            SearchUsed  = user.SearchUsed,
            Remaining   = unlimited ? int.MaxValue : Math.Max(0, user.SearchLimit - user.SearchUsed),
        });
    }

    [HttpGet("user/history")]
    public async Task<IActionResult> GetHistory()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var history = await _db.SearchHistories
            .Where(s => s.UserId == userId)
            .OrderByDescending(s => s.CreatedAt)
            .Take(50)
            .Select(s => new { s.Id, s.Keyword, s.Results, s.ResultCount, s.CreatedAt })
            .ToListAsync();

        return Ok(history);
    }

    private Guid? GetUserId()
    {
        var claim = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return Guid.TryParse(claim, out var id) ? id : null;
    }
}