namespace EbayHunter.API.DTOs;

// ── Auth ──────────────────────────────────────────────────────────────────────
public record RegisterRequest(string Email, string Password);
public record LoginRequest(string Email, string Password);
public record AuthResponse(string Token, string Email, string Role, int SearchLimit, int SearchUsed, int Remaining);

// ── Admin: create / manage users ─────────────────────────────────────────────
public record AdminCreateUserRequest(string Email, string Password, string Role);
public record TopUpRequest(int Amount);

// ── Search ────────────────────────────────────────────────────────────────────
public record SearchRequest(string Keyword);

public class ProductResult
{
    public string  Title            { get; set; } = string.Empty;
    public string  EbayUrl          { get; set; } = string.Empty;   // full specific listing URL
    public string  AliexpressUrl    { get; set; } = string.Empty;
    public decimal EbayPrice        { get; set; }
    public decimal AliexpressPrice  { get; set; }
    public decimal Profit           { get; set; }
    public int     SoldLastWeek     { get; set; }
    public int     Reviews          { get; set; }
    public bool    FreeShipping     { get; set; }
    public string  DeliveryDays     { get; set; } = string.Empty;
    public string  Country          { get; set; } = string.Empty;
    public string  Currency         { get; set; } = "USD";
}

public class SearchResponse
{
    public bool   Success            { get; set; }
    public string Keyword            { get; set; } = string.Empty;
    public List<ProductResult> Products { get; set; } = new();
    public int    TotalFound         { get; set; }
    public int    SearchesRemaining  { get; set; }
    public string? Error             { get; set; }
}

// ── User ──────────────────────────────────────────────────────────────────────
public class UserLimitsResponse
{
    public string Email       { get; set; } = string.Empty;
    public string Role        { get; set; } = string.Empty;
    public int    SearchLimit { get; set; }
    public int    SearchUsed  { get; set; }
    public int    Remaining   { get; set; }
}

// ── Admin ─────────────────────────────────────────────────────────────────────
public record UpdateRoleRequest(string Role);

public class AdminUserView
{
    public Guid   Id          { get; set; }
    public string Email       { get; set; } = string.Empty;
    public string Role        { get; set; } = string.Empty;
    public int    SearchLimit { get; set; }
    public int    SearchUsed  { get; set; }
    public int    Remaining   { get; set; }
    public DateTime CreatedAt { get; set; }
}