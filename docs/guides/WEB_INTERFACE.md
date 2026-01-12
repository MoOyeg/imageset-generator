# OpenShift ImageSetConfiguration Generator - Web Interface

A modern web-based interface for generating OpenShift ImageSetConfiguration files using React frontend and Flask backend.

## Architecture

- **Frontend**: React 18 with modern hooks and components
- **Backend**: Flask REST API with CORS support
- **Styling**: Custom CSS with OpenShift-inspired design
- **Build**: Create React App with production build optimization

## Quick Start

### Option 1: Automated Setup (Recommended)
```bash
./start-web.sh
```

### Option 2: Development Mode
```bash
./start-dev.sh
```

### Option 3: Docker
```bash
docker-compose up
```

## Manual Setup

### Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start Flask server
python app.py --host 127.0.0.1 --port 5000
```

### Frontend Setup
```bash
# Install Node.js dependencies
cd frontend
npm install

# For development (with hot reload)
npm start

# For production build
npm run build
```

## Features

### Web Interface Features
- **Tabbed Interface**: Organized sections for different configuration types
- **Real-time Preview**: Live YAML generation as you type
- **Drag & Drop**: Upload configuration files by dragging
- **Smart Validation**: Client and server-side validation
- **Responsive Design**: Works on desktop and mobile devices
- **Download Support**: Direct download of generated files

### API Features
- **RESTful Design**: Clean API endpoints for all operations
- **File Upload**: Support for JSON configuration file uploads
- **Validation**: Server-side validation with detailed error messages
- **CORS Support**: Enables frontend-backend communication
- **Health Checks**: Built-in health monitoring

## User Interface

### Basic Configuration Tab
- **OCP Versions**: Enter comma-separated version numbers
- **OCP Channel**: Select from predefined channels
- **Operators**: Add operators with smart suggestions
- **Quick Add Buttons**: One-click operator additions
- **Output File**: Specify generated file name

### Advanced Tab
- **Additional Images**: Container images to include
- **Helm Charts**: Add/remove Helm charts with repositories
- **Form Validation**: Real-time input validation

### Preview & Generate Tab
- **Configuration Summary**: Overview of current settings
- **YAML Preview**: Syntax-highlighted YAML output
- **Copy to Clipboard**: Easy sharing of generated content
- **Download**: Direct file download
- **Usage Instructions**: Commands for using with oc-mirror

### Load/Save Config Tab
- **File Upload**: Load JSON configuration files
- **Drag & Drop**: Drop files directly on the interface
- **Export Config**: Save current settings as JSON
- **Sample Config**: Load pre-defined examples
- **Reset**: Clear all configuration

## API Endpoints

### Configuration Management
- `POST /api/config/load` - Upload and load configuration file
- `POST /api/config/save` - Download current configuration as JSON
- `GET /api/config/sample` - Get sample configuration
- `POST /api/validate` - Validate configuration data

### Generation
- `POST /api/generate/preview` - Generate YAML preview
- `POST /api/generate/download` - Generate and download YAML file

### Utilities
- `GET /api/health` - Health check endpoint
- `GET /api/operators/mappings` - Get operator name mappings

## Configuration File Format

The web interface uses JSON configuration files:

```json
{
  "ocp_versions": ["4.14.1", "4.14.2"],
  "ocp_channel": "stable-4.14",
  "operators": ["logging", "monitoring", "pipelines"],
  "operator_catalog": "registry.redhat.io/redhat/redhat-operator-index",
  "additional_images": ["registry.redhat.io/ubi8/ubi:latest"],
  "helm_charts": [
    {
      "name": "prometheus",
      "repository": "https://prometheus-community.github.io/helm-charts",
      "version": "15.0.0"
    }
  ],
  "output_file": "imageset-config.yaml"
}
```

## Environment Variables

### Flask Backend
- `FLASK_ENV`: Set to `development` or `production`
- `FLASK_HOST`: Host to bind to (default: 127.0.0.1)
- `FLASK_PORT`: Port to bind to (default: 5000)

### React Frontend (development)
- `REACT_APP_API_URL`: Backend API URL (auto-detected in production)
- `PORT`: Development server port (default: 3000)

## Development

### Project Structure
```
frontend/
├── public/
│   └── index.html          # HTML template
├── src/
│   ├── App.js              # Main application component
│   ├── index.js            # React entry point
│   ├── index.css           # Global styles
│   └── components/
│       ├── BasicConfig.js  # Basic configuration form
│       ├── AdvancedConfig.js # Advanced options form
│       ├── PreviewGenerate.js # Preview and generation
│       ├── LoadSaveConfig.js # File operations
│       └── StatusBar.js    # Status display
├── package.json            # Node.js dependencies
└── build/                  # Production build output
```

### Development Workflow

1. **Start development servers**:
   ```bash
   ./start-dev.sh
   ```

2. **Make changes** to React components in `frontend/src/`

3. **Test API changes** by modifying `app.py`

4. **Build for production**:
   ```bash
   cd frontend && npm run build
   ```

### Adding New Features

#### Frontend Component
1. Create new component in `frontend/src/components/`
2. Import and use in `App.js`
3. Add required state management
4. Style with CSS classes

#### Backend Endpoint
1. Add route function in `app.py`
2. Implement request/response handling
3. Add error handling and validation
4. Update API documentation

## Deployment Options

### Traditional Server
```bash
# Build frontend
cd frontend && npm run build && cd ..

# Start production server
python app.py --host 0.0.0.0 --port 5000
```

### Docker
```bash
# Build and run
docker-compose up

# Development mode
docker-compose --profile dev up
```

### Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Security Considerations

- **Input Validation**: All inputs are validated on both client and server
- **File Upload Limits**: JSON files only, size limits enforced
- **CORS Configuration**: Properly configured for production
- **No Authentication**: Currently open access (add auth if needed)

## Performance

- **Frontend Optimization**: Production build with minification
- **API Efficiency**: Minimal data transfer with focused endpoints
- **Caching**: Static assets cached by browser
- **Responsive**: Optimized for various screen sizes

## Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Find process using port 5000
   lsof -i :5000
   # Kill the process
   kill -9 <PID>
   ```

2. **Node.js/npm not found**:
   ```bash
   # Install Node.js (Ubuntu/Debian)
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

3. **Python dependencies issues**:
   ```bash
   # Clean install
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Frontend build fails**:
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   npm run build
   ```

### Debug Mode

Enable debug logging:
```bash
python app.py --debug
```

Check browser developer tools for frontend issues.

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Update documentation
5. Submit pull request

## License

MIT License - see LICENSE file for details.
