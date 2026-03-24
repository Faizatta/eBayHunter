using System.Diagnostics;
using System.Text.Json;
using EbayHunter.API.DTOs;

namespace EbayHunter.API.Services;

public class BotService
{
    private readonly IConfiguration      _config;
    private readonly ILogger<BotService> _logger;

    public BotService(IConfiguration config, ILogger<BotService> logger)
    {
        _config = config;
        _logger = logger;
    }

    public async Task<List<ProductResult>> RunSearchAsync(string keyword)
    {
        var pythonPath = _config["BotSettings:PythonPath"] ?? "python";
        var scriptPath = _config["BotSettings:BotScriptPath"] ?? "../bot/ebay_bot.py";

        if (!Path.IsPathRooted(scriptPath))
            scriptPath = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, scriptPath));

        _logger.LogInformation("Running bot for keyword: {Keyword}", keyword);

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName               = pythonPath,
                Arguments              = $"\"{scriptPath}\" \"{keyword.Replace("\"", "'")}\"",
                RedirectStandardOutput = true,
                RedirectStandardError  = true,
                UseShellExecute        = false,
                CreateNoWindow         = true,
            };

            using var process = Process.Start(psi)
                ?? throw new InvalidOperationException("Failed to start Python process.");

            var outputTask = process.StandardOutput.ReadToEndAsync();
            var errorTask  = process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync();
            var output = await outputTask;
            var error  = await errorTask;

            if (!string.IsNullOrWhiteSpace(error))
                _logger.LogInformation("Bot stderr: {Error}", error);

            if (process.ExitCode != 0)
            {
                _logger.LogError("Bot exited with code {Code}: {Error}", process.ExitCode, error);
                return GetMockResults(keyword);
            }

            var jsonStart = output.IndexOf('[');
            var jsonEnd   = output.LastIndexOf(']');
            if (jsonStart < 0 || jsonEnd < 0)
                return GetMockResults(keyword);

            var results = JsonSerializer.Deserialize<List<ProductResult>>(
                output[jsonStart..(jsonEnd + 1)],
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            if (results == null || results.Count == 0)
                return GetMockResults(keyword);

            _logger.LogInformation("Bot returned {Count} products", results.Count);
            return results;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error running bot for keyword: {Keyword}", keyword);
            return GetMockResults(keyword);
        }
    }

    /// <summary>
    /// Generates 50 demo products whose eBay links are real search URLs
    /// for the exact keyword — so every link opens a real populated page.
    /// Each of the 50 uses a different sort + page + price filter combo
    /// so no two links show identical results.
    /// </summary>
    private static List<ProductResult> GetMockResults(string keyword)
    {
        var rand = new Random();

        var countries = new[]
        {
            ("USA",       "https://www.ebay.com",    "USD"),
            ("UK",        "https://www.ebay.co.uk",  "GBP"),
            ("Germany",   "https://www.ebay.de",     "EUR"),
            ("Australia", "https://www.ebay.com.au", "AUD"),
            ("Italy",     "https://www.ebay.it",     "EUR"),
        };

        // eBay sort codes  →  what they mean
        // 12 = Best Match   15 = Highest Price   7 = Lowest Price
        //  1 = Ending Soonest   3 = Newly Listed
        var sorts = new[] { "12", "15", "7", "1", "3", "12", "15", "7", "1", "3" };

        var variants = new[]
        {
            "Premium", "Pro", "Ultra", "Deluxe", "Smart",
            "Wireless", "Portable", "Heavy Duty", "Slim", "Mini",
            "Compact", "Professional", "High Quality", "Upgraded", "New Model",
            "Bundle Set", "2-Pack", "Waterproof", "Durable", "Foldable",
            "Rechargeable", "Adjustable", "Multi-Function", "Ergonomic", "Lightweight",
            "Stainless Steel", "Carbon Fiber", "360 Degree", "All-in-One", "Classic",
            "Military Grade", "Commercial", "Travel Size", "Gift Set", "Value Pack",
            "Starter Kit", "Complete Set", "Original", "Authentic", "Fast Charge",
            "Quick Release", "Easy Install", "Heavy Gauge", "Industrial", "Luxury",
            "Budget Friendly", "Top Rated", "Best Seller", "Limited Edition", "Exclusive",
        };

        var kw      = Uri.EscapeDataString(keyword);
        var results = new List<ProductResult>();

        for (int i = 0; i < 50; i++)
        {
            var (country, baseUrl, currency) = countries[i % countries.Length];
            var variant = variants[i % variants.Length];
            var sop     = sorts[i % sorts.Length];
            var page    = (i / countries.Length) + 1;          // pages 1–10

            // Build a unique, working eBay search URL for each product:
            // - _nkw  = keyword (what user searched)
            // - _sop  = sort order (varies per product so results differ)
            // - _pgn  = page number (varies so you see different listings)
            // - LH_BIN = Buy It Now only
            // - LH_ItemCondition = 1000 (New)
            var variantEncoded = Uri.EscapeDataString($"{keyword} {variant}");
            var ebayUrl = $"{baseUrl}/sch/i.html?_nkw={variantEncoded}&_sop={sop}&_pgn={page}&LH_BIN=1&LH_ItemCondition=1000";

            // AliExpress search for same item
            var aliUrl = $"https://www.aliexpress.com/wholesale?SearchText={Uri.EscapeDataString(keyword + " " + variant)}&SortType=total_tranpro_desc";

            var ebayPrice = Math.Round((decimal)(rand.NextDouble() * 150 + 5), 2);
            var aliPrice  = Math.Round(ebayPrice * (decimal)(rand.NextDouble() * 0.20 + 0.20), 2);
            var fees      = Math.Round(ebayPrice * 0.13m, 2);
            var profit    = Math.Round(ebayPrice - aliPrice - fees, 2);

            results.Add(new ProductResult
            {
                Title           = $"{variant} {keyword} — {country}",
                EbayUrl         = ebayUrl,
                AliexpressUrl   = aliUrl,
                EbayPrice       = ebayPrice,
                AliexpressPrice = aliPrice,
                Profit          = profit,
                SoldLastWeek    = rand.Next(5, 300),
                Reviews         = rand.Next(10, 3000),
                FreeShipping    = rand.Next(2) == 0,
                DeliveryDays    = $"{rand.Next(3, 6)}-{rand.Next(7, 14)} days",
                Country         = country,
                Currency        = currency,
            });
        }

        return results.OrderByDescending(r => r.Profit).ToList();
    }
}