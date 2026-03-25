using Microsoft.AspNetCore.Mvc;
using EbayHunter.API.DTOs;
using EbayHunter.API.Services;

namespace EbayHunter.API.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly AuthService _authService;

    public AuthController(AuthService authService)
    {
        _authService = authService;
    }

    /// <summary>Register a new user</summary>
    [HttpPost("register")]
    public async Task<IActionResult> Register([FromBody] RegisterRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
            return BadRequest(new { error = "Email and password are required." });

        var (success, message, response) = await _authService.RegisterAsync(request);
        if (!success)
            return BadRequest(new { error = message });

        return Ok(new { message, data = response });
    }

    /// <summary>Login with email and password</summary>
    [HttpPost("login")]
    public async Task<IActionResult> Login([FromBody] LoginRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Email) || string.IsNullOrWhiteSpace(request.Password))
            return BadRequest(new { error = "Email and password are required." });

        var (success, message, response) = await _authService.LoginAsync(request);
        if (!success)
            return Unauthorized(new { error = message });

        return Ok(new { message, data = response });
    }
}
