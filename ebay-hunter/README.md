# eBay Hunter — SaaS Product Research Bot

A full-stack SaaS application for finding profitable eBay dropshipping opportunities by comparing eBay prices against AliExpress sourcing costs.

```
┌─────────────────────────────────────────────────────────────┐
│  Vue.js Frontend (Port 5173)                                │
│  Login · Dashboard · Admin Panel · Search History          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP / REST API
┌──────────────────────▼──────────────────────────────────────┐
│  ASP.NET Core Backend (Port 5000)                           │
│  JWT Auth · Role Guards · Search Limit Enforcement         │
└──────────────────────┬──────────────────────────────────────┘
          ┌────────────┴────────────┐
          │                         │
┌─────────▼──────────┐   ┌─────────▼──────────┐
│  PostgreSQL DB     │   │  Python Bot        │
│  Users · History   │   │  eBay + AliExpress │
└────────────────────┘   │  Playwright        │
                         └────────────────────┘
```

---

## Project Structure

```
ebay-hunter/
├── backend/                  # C# ASP.NET Core 8 API
│   ├── Controllers/
│   │   ├── AuthController.cs     POST /register, POST /login
│   │   ├── SearchController.cs   POST /search, GET /user/limits, GET /user/history
│   │   └── AdminController.cs    Admin CRUD + stats
│   ├── Services/
│   │   ├── AuthService.cs        JWT auth, BCrypt hashing
│   │   └── BotService.cs         Python process runner
│   ├── Models/
│   │   ├── User.cs
│   │   └── SearchHistory.cs
│   ├── Data/AppDbContext.cs
│   ├── DTOs/Dtos.cs
│   ├── Program.cs
│   └── appsettings.json
│
├── frontend/                 # Vue 3 + Tailwind CSS
│   ├── src/
│   │   ├── views/
│   │   │   ├── LoginView.vue
│   │   │   ├── RegisterView.vue
│   │   │   ├── DashboardView.vue     Main search UI
│   │   │   ├── HistoryView.vue       Past searches
│   │   │   └── AdminView.vue         Admin panel
│   │   ├── stores/auth.js            Pinia auth state
│   │   ├── router/index.js           Vue Router + guards
│   │   ├── api/index.js              Axios client
│   │   └── App.vue                   Sidebar layout
│   ├── index.html
│   └── package.json
│
├── bot/                      # Python Playwright scraper
│   ├── ebay_bot.py
│   └── requirements.txt
│
└── database/
    └── schema.sql            PostgreSQL schema
```

---

## Role & Search Limits

| Role  | Daily Searches | Notes           |
|-------|---------------|-----------------|
| Free  | 5             | Default on signup |
| Basic | 20            | Upgraded by admin |
| Pro   | 100           | Power users      |
| Admin | Unlimited     | Full access      |

Limits reset **daily** (auto-detected on login/search).

---

## API Endpoints

| Method | Path                         | Auth    | Description              |
|--------|------------------------------|---------|--------------------------|
| POST   | `/api/auth/register`         | No      | Register new user        |
| POST   | `/api/auth/login`            | No      | Login, get JWT           |
| POST   | `/api/search`                | JWT     | Run product search       |
| GET    | `/api/user/limits`           | JWT     | Get search usage         |
| GET    | `/api/user/history`          | JWT     | Get past searches        |
| GET    | `/api/admin/users`           | Admin   | List all users           |
| PUT    | `/api/admin/users/{id}/role` | Admin   | Change user role         |
| POST   | `/api/admin/users/{id}/reset`| Admin   | Reset search limit       |
| GET    | `/api/admin/stats`           | Admin   | Bot usage statistics     |

---

## Setup & Running

### Prerequisites

- [.NET 8 SDK](https://dotnet.microsoft.com/download)
- [Node.js 18+](https://nodejs.org/)
- [PostgreSQL 14+](https://www.postgresql.org/)
- [Python 3.10+](https://python.org/)

---

### 1️⃣ Database Setup

```bash
# Start PostgreSQL and create the database
psql -U postgres

CREATE DATABASE ebayhunter;
\q

# Run schema
psql -U postgres -d ebayhunter -f database/schema.sql
```

The schema creates `users` and `search_history` tables plus a default admin:
- Email: `admin@ebayhunter.com`
- Password: `Admin@123`

---

### 2️⃣ Backend Setup (C# ASP.NET Core)

```bash
cd backend

# Edit connection string in appsettings.json
# Change: "Host=localhost;Port=5432;Database=ebayhunter;Username=postgres;Password=yourpassword"

# Restore packages
dotnet restore

# Run migrations (first time only)
dotnet ef migrations add InitialCreate
dotnet ef database update

# OR just use the SQL schema file directly (no migrations needed)

# Start the API server
dotnet run

# API runs at http://localhost:5000
# Swagger UI at http://localhost:5000/swagger
```

> **Note:** If you use the SQL schema file directly, comment out `db.Database.Migrate()` in `Program.cs`.

---

### 3️⃣ Python Bot Setup

```bash
cd bot

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (one-time)
playwright install chromium

# Test the bot manually
python ebay_bot.py "wireless earbuds"
# Should output JSON array of products
```

The bot is called automatically by the backend when a search runs.
Make sure the path in `appsettings.json` points to your bot script:
```json
"BotSettings": {
  "PythonPath": "python3",
  "BotScriptPath": "../bot/ebay_bot.py"
}
```

---

### 4️⃣ Frontend Setup (Vue.js)

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Frontend runs at http://localhost:5173
```

The Vite dev server proxies `/api` requests to `http://localhost:5000` automatically.

For production build:
```bash
npm run build
# Static files in frontend/dist/
```

---

## Running All Three Together

Open three terminals:

**Terminal 1 — Backend:**
```bash
cd ebay-hunter/backend && dotnet run
```

**Terminal 2 — Frontend:**
```bash
cd ebay-hunter/frontend && npm run dev
```

**Terminal 3 — (Optional) Test bot directly:**
```bash
cd ebay-hunter/bot && python ebay_bot.py "phone case"
```

Then open: **http://localhost:5173**

---

## Development Notes

### Mock Data Fallback
If the Python bot is not running or Playwright is not installed, the `BotService` automatically returns **realistic mock data** so you can develop and test the frontend without needing the bot running.

### Profit Calculation
```
profit = eBay_price - AliExpress_price - (eBay_price × 13%)
```
eBay charges ~13% in final value fees + payment processing.

### Bot Filter Criteria
Products must pass **all** of these:
- Sold ≥ 4 in the last week
- Reviews ≥ 50
- Free shipping
- Delivery within 3–7 days

### Countries Searched (in order)
1. 🇩🇪 Germany (ebay.de)
2. 🇬🇧 UK (ebay.co.uk)
3. 🇮🇹 Italy (ebay.it)
4. 🇺🇸 USA (ebay.com)
5. 🇦🇺 Australia (ebay.com.au)

---

## Environment Variables

For production, override `appsettings.json` values with environment variables:

```bash
export ConnectionStrings__DefaultConnection="Host=prod-db;..."
export Jwt__SecretKey="your-32-char-production-secret-key"
export BotSettings__PythonPath="/usr/bin/python3"
export BotSettings__BotScriptPath="/app/bot/ebay_bot.py"
```

---

## Troubleshooting

**Bot returns empty results:**
- Ensure Playwright is installed: `playwright install chromium`
- eBay may be rate-limiting; try adding more delays in `ebay_bot.py`
- The mock data fallback will kick in automatically

**JWT errors:**
- Ensure `Jwt:SecretKey` is at least 32 characters
- Check clock skew between server and client

**CORS errors:**
- Add your frontend URL to `Cors:AllowedOrigins` in `appsettings.json`

**Database connection:**
- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `appsettings.json`
