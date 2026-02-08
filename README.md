# Teacher Interaction Module - Setup Guide

## Python Version Requirements
- **Recommended**: Python 3.11 or higher (better Tkinter support on macOS)
- **Minimum**: Python 3.9.6

> **Important**: Python 3.11 provides significantly better Tkinter compatibility on macOS, especially for GUI rendering and widget visibility.

## Installing Python 3.11 on macOS

### Method 1: Direct Download from python.org (Recommended if Homebrew not installed)

1. **Download Python 3.11**
   - Visit: https://www.python.org/downloads/release/python-31110/
   - Scroll to "Files" section
   - Download: `macOS 64-bit universal2 installer`

2. **Install Python 3.11**
   - Open the downloaded `.pkg` file
   - Follow the installation wizard
   - Complete all steps

3. **Verify Installation**
   ```bash
   python3.11 --version
   # Should output: Python 3.11.10 (or similar)
   ```

4. **Update pip for Python 3.11**
   ```bash
   python3.11 -m pip install --upgrade pip
   ```

### Method 2: Using Homebrew (if available)

```bash
# Install Homebrew first (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Verify
python3.11 --version
```

## Installing Dependencies

After installing Python 3.11, install the required packages:

```bash
cd /Users/hershey/Desktop/TeacherInteractionModule/server
python3.11 -m pip install flask flask-socketio flask-cors pyaudio pymupdf pillow
```

## Running the Application

### With Python 3.11 (Strongly Recommended)
```bash
cd /Users/hershey/Desktop/TeacherInteractionModule/server
python3.11 main.py
```

### With Python 3.9+ (Current - Not Recommended)
```bash
cd /Users/hershey/Desktop/TeacherInteractionModule/server
python3 main.py
```

## Troubleshooting

### Issue: Sidebar content not visible
- **Solution**: Use Python 3.11 - it has better Tkinter support on macOS
- The grid layout and canvas rendering work more reliably with Python 3.11

### Issue: "python3.11 not found"
- **Solution**: Make sure you completed the installation steps above
- Try: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 main.py`

### Issue: Tkinter deprecation warnings
- **Solution**: These are system warnings from macOS - they don't affect functionality
- Python 3.11 handles Tkinter better despite these warnings
