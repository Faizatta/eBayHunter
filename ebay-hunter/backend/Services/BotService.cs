using System.Diagnostics;
using System.Text.Json;
using EbayHunter.API.DTOs;

namespace EbayHunter.API.Services;

public class BotService
{
    private readonly IConfiguration _config;
    private readonly ILogger<BotService> _logger;

    public BotService(IConfiguration config, ILogger<BotService> logger)
    {
        _config = config;
        _logger = logger;
    }

    public async Task<List<ProductResult>> RunSearchAsync(string keyword)
    {
        var pythonPath = _config["BotSettings:PythonPath"] ?? "python3";
        var scriptPath = _config["BotSettings:BotScriptPath"] ?? "../bot/ebay_bot.py";

        // Resolve script path relative to app
        if (!Path.IsPathRooted(scriptPath))
        {
            var baseDir = AppContext.BaseDirectory;
            scriptPath = Path.GetFullPath(Path.Combine(baseDir, scriptPath));
        }

        _logger.LogInformation("Running bot for keyword: {Keyword}", keyword);

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = pythonPath,
                Arguments = $"\"{scriptPath}\" \"{keyword.Replace("\"", "'")}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            using var process = Process.Start(psi)
                ?? throw new InvalidOperationException("Failed to start Python process.");

            var output = await process.StandardOutput.ReadToEndAsync();
            var error = await process.StandardError.ReadToEndAsync();

            await process.WaitForExitAsync();

            if (process.ExitCode != 0)
            {
                _logger.LogError("Bot exited with code {Code}: {Error}", process.ExitCode, error);
                // Return mock data for demo purposes when bot fails
                return GetMockResults(keyword);
            }

            // Parse JSON output from Python bot
            var results = JsonSerializer.Deserialize<List<ProductResult>>(output,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

            return results ?? new List<ProductResult>();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error running bot for keyword: {Keyword}", keyword);
            // Return mock data so the API remains functional during development
            return GetMockResults(keyword);
        }
    }

    // Mock data for development / when bot is not running
    private static List<ProductResult> GetMockResults(string keyword)
    {
        var rand = new Random();
        var countries = new[] { "Germany", "UK", "Italy", "USA", "Australia" };
        var results = new List<ProductResult>();

        for (int i = 0; i < rand.Next(3, 8); i++)
        {
            var ebayPrice = Math.Round((decimal)(rand.NextDouble() * 80 + 20), 2);
            var aliPrice  = Math.Round(ebayPrice * (decimal)(rand.NextDouble() * 0.3 + 0.3), 2);
            var fees      = Math.Round(ebayPrice * 0.13m, 2);
            var profit    = Math.Round(ebayPrice - aliPrice - fees, 2);

            results.Add(new ProductResult
            {
                Title         = $"{keyword} - Sample Product {i + 1} (High Quality)",
                EbayUrl       = $"https://www.ebay.com/sch/i.html?_nkw={Uri.EscapeDataString(keyword)}&item={rand.Next(100000, 999999)}",
                AliexpressUrl = $"https://www.aliexpress.com/wholesale?SearchText={Uri.EscapeDataString(keyword)}",
                EbayPrice     = ebayPrice,
                AliexpressPrice = aliPrice,
                Profit        = profit,
                SoldLastWeek  = rand.Next(4, 50),
                Reviews       = rand.Next(50, 500),
                FreeShipping  = true,
                DeliveryDays  = $"{rand.Next(3, 5)}-{rand.Next(5, 8)} days",
                Country       = countries[rand.Next(countries.Length)],
                Currency      = "USD"
            });
        }

        return results.Where(r => r.Profit > 0).ToList();
    }
}
