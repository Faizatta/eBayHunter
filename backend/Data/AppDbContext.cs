using Microsoft.EntityFrameworkCore;
using EbayHunter.API.Models;

namespace EbayHunter.API.Data;

public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    public DbSet<User>          Users           => Set<User>();
    public DbSet<SearchHistory> SearchHistories => Set<SearchHistory>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<User>(e =>
        {
            e.ToTable("users");
            e.HasKey(u => u.Id);
            e.Property(u => u.Id).HasColumnName("id");
            e.Property(u => u.Email).HasColumnName("email").IsRequired().HasMaxLength(255);
            e.Property(u => u.PasswordHash).HasColumnName("password_hash").IsRequired();
            e.Property(u => u.Role).HasColumnName("role").HasMaxLength(20);
            e.Property(u => u.SearchLimit).HasColumnName("search_limit");
            e.Property(u => u.SearchUsed).HasColumnName("search_used");
            e.Property(u => u.LastResetDate).HasColumnName("last_reset_date");
            e.Property(u => u.CreatedAt).HasColumnName("created_at");
            e.Property(u => u.UpdatedAt).HasColumnName("updated_at");
            e.HasIndex(u => u.Email).IsUnique();
        });

        modelBuilder.Entity<SearchHistory>(e =>
        {
            e.ToTable("search_history");
            e.HasKey(s => s.Id);
            e.Property(s => s.Id).HasColumnName("id");
            e.Property(s => s.UserId).HasColumnName("user_id");
            e.Property(s => s.Keyword).HasColumnName("keyword");
            e.Property(s => s.Results).HasColumnName("results").HasColumnType("jsonb");
            e.Property(s => s.ResultCount).HasColumnName("result_count");
            e.Property(s => s.CreatedAt).HasColumnName("created_at");
            e.HasOne(s => s.User)
             .WithMany(u => u.SearchHistories)
             .HasForeignKey(s => s.UserId);
        });
    }
}