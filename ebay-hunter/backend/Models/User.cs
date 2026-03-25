namespace EbayHunter.API.Models;

public class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public string Role { get; set; } = "Free";
    public int SearchLimit { get; set; } = 5;
    public int SearchUsed { get; set; } = 0;
    public DateOnly LastResetDate { get; set; } = DateOnly.FromDateTime(DateTime.UtcNow);
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    // Navigation
    public ICollection<SearchHistory> SearchHistories { get; set; } = new List<SearchHistory>();
}
