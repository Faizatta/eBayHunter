namespace EbayHunter.API.Models;

public class SearchHistory
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid UserId { get; set; }
    public string Keyword { get; set; } = string.Empty;
    public string? Results { get; set; }  // JSON string
    public int ResultCount { get; set; } = 0;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    // Navigation
    public User User { get; set; } = null!;
}
