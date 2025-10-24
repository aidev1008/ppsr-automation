# PPSR Automation API

A FastAPI-based automation service for the Australian Personal Property Securities Register (PPSR) system. This service automates the process of logging into the PPSR portal, performing VIN-based searches, and extracting vehicle registration plate numbers.

## Features

- 🤖 **Automated PPSR Login**: Secure login with username/password authentication
- 🔍 **VIN Search**: Search vehicles by Vehicle Identification Number (VIN)
- 📛 **Plate Extraction**: Automatically extract registration plate numbers from search results
- 🎭 **Human-like Behavior**: Implements realistic typing speeds, delays, and mouse movements
- 📊 **Comprehensive Logging**: Detailed logging with request tracking and screenshots
- 🔍 **Playwright Tracing**: Full execution traces for debugging and analysis
- 🌐 **RESTful API**: Easy integration via HTTP endpoints
- ⚡ **Async Support**: Built with async/await for optimal performance

## Technology Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **Playwright**: Reliable browser automation with Chromium
- **Pydantic**: Data validation and settings management
- **Python-dotenv**: Environment variable management
- **Uvicorn**: Lightning-fast ASGI server

## Installation

### Prerequisites

- Python 3.8+
- Windows, macOS, or Linux

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/aidev1008/ppsr-automation.git
   cd ppsr-automation
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirement.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Environment Configuration**
   Create a `.env` file in the project root:
   ```env
   HEADLESS=true
   # Set to false for debugging with visible browser
   ```
5. **To Run The Project**
    python -m uvicorn ppsr:app --host 0.0.0.0 --port 8000
    
## Usage

### Starting the Server

```bash
python ppsr.py
```

The API will be available at `http://localhost:8000`

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

### API Endpoints

#### POST /open_ppsr

Automates PPSR login and VIN search process.

**Request Body:**
```json
{
  "username": "your_ppsr_username",
  "password": "your_ppsr_password",
  "vin_number": "1HGCM82633A123456",
  "plate_number": null
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Login attempt completed",
  "plateNumber": "ABC123",
  "requestId": "a1b2c3d4",
  "logsDir": "/path/to/logs/a1b2c3d4",
  "trace": "/path/to/trace-a1b2c3d4.zip"
}
```

#### GET /

Health check endpoint.

**Response:**
```json
{
  "message": "PPSR Automation API is running"
}
```

### Example Usage

**Using curl:**
```bash
curl -X POST "http://localhost:8000/open_ppsr" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "your_username",
       "password": "your_password",
       "vin_number": "1HGCM82633A123456"
     }'
```

**Using Python requests:**
```python
import requests

response = requests.post(
    "http://localhost:8000/open_ppsr",
    json={
        "username": "your_username",
        "password": "your_password",
        "vin_number": "1HGCM82633A123456"
    }
)

result = response.json()
print(f"Plate Number: {result['plateNumber']}")
```

## Configuration

### Environment Variables

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `HEADLESS` | Run browser in headless mode | `true` | `true`, `false` |

### Automation Settings

The following settings can be adjusted in `ppsr.py`:

- `SLOW_MO_MS`: Delay between Playwright actions (default: 1500ms)
- `WAIT_AFTER_ACTION_MS`: Base wait time between major steps (default: 2400ms)
- Human typing delays: 120-220ms per character

## Logging and Debugging

### Log Files

- **Location**: `./logs/`
- **Format**: Daily rotating logs with 7-day retention
- **Content**: Detailed execution logs with timestamps and request IDs

### Screenshots

Automatic screenshots are captured at key stages:
- Initial page load
- After login
- After menu navigation
- After VIN entry
- Search results
- Error states

### Playwright Traces

Complete execution traces are saved for each request:
- **Location**: `./logs/{request_id}/trace-{request_id}.zip`
- **Usage**: Open with `playwright show-trace trace-file.zip`

## Development

### Project Structure

```
ppsr-automation/
├── ppsr.py              # Main application file
├── requirement.txt      # Python dependencies
├── README.md           # Project documentation
├── .env                # Environment configuration
└── logs/               # Generated logs and traces
    └── {request_id}/   # Per-request artifacts
        ├── *.png       # Screenshots
        └── trace-*.zip # Playwright traces
```

### Testing

Run the development server with auto-reload:
```bash
uvicorn ppsr:app --reload --host 0.0.0.0 --port 8000
```

### Debugging

1. Set `HEADLESS=false` in `.env` to see browser actions
2. Check logs in `./logs/ppsr.log`
3. Review screenshots in request-specific log directories
4. Analyze Playwright traces with `playwright show-trace`

## Security Considerations

- 🔒 Credentials are not logged or stored
- 🛡️ Each request runs in an isolated browser context
- 🔐 Environment variables for sensitive configuration
- 📝 Request tracking with unique IDs for audit trails

## Troubleshooting

### Common Issues

**Browser Launch Failures:**
- Ensure Playwright browsers are installed: `playwright install chromium`
- Check system requirements for Chromium

**Login Failures:**
- Verify PPSR credentials
- Check if PPSR site structure has changed
- Review screenshots in logs directory

**VIN Search Issues:**
- Ensure VIN format is correct (17 characters)
- Check if declaration checkbox is being ticked
- Review Playwright trace for detailed execution flow

**Network Issues:**
- Check internet connectivity
- Verify PPSR site accessibility
- Review request failure logs

### Support

For issues and questions:
1. Check the logs directory for detailed error information
2. Review Playwright traces for execution details
3. Create an issue with relevant log excerpts and error messages

## License

This project is for educational and automation purposes. Please ensure compliance with PPSR terms of service and applicable regulations.

## Disclaimer

This automation tool is designed to interact with the PPSR system in a responsible manner, mimicking human behavior to avoid detection. Users are responsible for ensuring their usage complies with PPSR terms of service and applicable laws.