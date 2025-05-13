# **The SacraDavis York Times**

A copy of the NYT homepage, built for HW2 of ECS 162 @ UC Davis.

<small style = "font-size: 0.75em"> ** Project based off the <code style="color: orangered">npx sv create</code> template. See below.</small>

```bash
    npx sv create my-app
    # Options: Minimal SvelteKit, TypeScript support, vite, npm
    #  {eslint, prettier, tailwind, svelte-adapter}, vitest, playwrite.test
    cd 'app-name' 
    npm install
    npm run dev
 ```
## Table of Contents

*   [Prerequisites](#prerequisites)
*   [Project Setup](#project-setup)
*   [Dev Environment Setup](#dev-environment-setup)
    *   [Build from Docker](#build-from-docker)
    *   [Using the Terminal](#using-the-terminal)
    *   [Using VS Code Launch Configurations](#using-vs-code-launch-configurations)

## Prerequisites

*   **Node.js:** Version 18 or higher (comes with npm). [Download Node.js](https://nodejs.org/)
*   **Python:** Version 3.10 or higher (comes with pip). [Download Python](https://python.org/)
*   ~~**Docker:** [Install Docker](https://docs.docker.com/get-docker/)~~ **DEPRECATED**

### VS Code Extensions

*    [**Python**](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
*    [**Svelte for VS Code**](https://marketplace.visualstudio.com/items?itemName=svelte.svelte-vscode)
*    [**Volar**](https://marketplace.visualstudio.com/items?itemName=Vue.volar)

## Project Setup

Follow these steps to set up the project environment locally:

1.  **Clone repo:**
    ```bash
    git clone [Your Repository URL]
    cd [Your Project Directory Name]
    ```

2.  **Frontend Setup:**
    ```bash
    cd frontend
    npm install
    cd ..
    ```
    This installs all the Node.js dependencies required for the Svelte frontend.

3.  **Set up the Backend:**
    ```bash
    cd backend

    # Python virtual environment (recommended)
    # Used for the local building process, docker handles submission build process.
    python -m venv venv  # python3 on some systems

    # Activate the virtual environment
    # On macOS/Linux:
    source venv/bin/activate
    # On Windows (Command Prompt):
    venv\Scripts\activate.bat
    # On Windows (PowerShell or Git Bash):
    venv\Scripts\activate

    # Python dependencies
    pip install -r requirements.txt
    
    cd ..
    ```
    *Note: Remember to activate the virtual environment (`source backend/venv/bin/activate` or `backend\venv\Scripts\activate`) every time you open a new terminal session to work on the backend.*

## Dev Environment Setup

You can run the frontend and backend development servers separately for a better development experience with features like hot-reloading.

### Build from Docker
- Dev:
    * ```bash 
        docker-compose -f docker-compose.dev.yml up --build 
      ```
- Prod:
    * ```bash 
        docker-compose -f docker-compose.prod.yml up --build 
      ```



### Using the Terminal

You'll need two separate terminal windows/tabs:

1.  **Terminal 1: Run the Backend (Flask):**
    ```bash
    cd backend

    # Activate virtual environment if not already active
    # macOS/Linux: source venv/bin/activate
    # Windows: venv\Scripts\activate

    # Set environment variables (important for Flask)
    # macOS/Linux:
    export PORT=8000
    export FLASK_ENV=development # Enables debug mode & auto-reloading

    # Windows (Command Prompt):
    set PORT=8000
    set FLASK_ENV=development

    # Windows (PowerShell):
    $env:PORT="8000"
    $env:FLASK_ENV="development"

    # Run the Flask app
    python app.py
    ```
    The backend API is now running on `http://localhost:8000`.

2.  **Terminal 2: Run the Frontend (Svelte Dev Server):**
    ```bash
    cd frontend
    npm run dev
    ```
    The Svelte development server will start. Look for output similar to `Local: http://localhost:5173/` (the port number might vary).

3.  **Access the App:** Open your web browser and navigate to the URL provided by the **frontend** dev server (e.g., `http://localhost:5173`).

    *Note: The Flask backend needs `flask-cors` configured, or the Svelte dev server needs a proxy set up to handle Cross-Origin Resource Sharing (CORS) correctly during local development.*
    * Professor handled this in template code *

### VS Code Launch Configurations

1. **Create a `launch.json` file:**
    *   Create a folder named `.vscode` in the root directory of your project if it doesn't exist.
    *   Inside the `.vscode` folder, create a file named `launch.json`.
    *   Paste the following content into `launch.json`:
         * ***DELETE COMMENTS - JSON WONT WORK***

```json
    {
  // Use IntelliSense to learn about possible attributes.
  // Hover to view descriptions of existing attributes.
  // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
  "version": "0.2.0",
  "configurations": [
    {
      // Configuration for running the Python Flask backend
      "name": "Python: Run-Flask-Backend",
      "type": "python",
      "request": "launch",
      // Points to the main Flask application file. Adjust if your backend is nested deeper.
      "program": "${workspaceFolder}/backend/app.py",
      // Sets the current working directory for the script. Adjust if nested deeper.
      "cwd": "${workspaceFolder}/backend",
      // Environment variables needed by the Flask app.
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PORT": "8000",
        "FLASK_ENV": "development", // Enables debug mode, automatic reloading
        "FLASK_APP": "app.py"       // Explicitly tells Flask which file/app instance to run
      },
      // Tells VS Code to use the Python interpreter selected for the workspace.
      // *** IMPORTANT: Select the Python interpreter from 'backend/venv' ***
    {
      "python": "${command:python.interpreterPath}",
      "jinja": true, // Enable Jinja template debugging if needed
      "justMyCode": true, // Step through user-written code only by default
      "console": "integratedTerminal" // Show output in the integrated VS Code terminal
    },
    {
      // Configuration for running the Svelte frontend development server
      "name": "NPM: Run-Svelte-Frontend-Dev",
      "type": "npm", // Use the built-in npm type
      "request": "launch",
      // The npm script to execute (from frontend/package.json)
      "script": "dev",
      // Sets the current working directory for the npm script. Adjust if nested deeper.
      "cwd": "${workspaceFolder}/frontend",
      // Shows output in the integrated VS Code terminal
      "console": "integratedTerminal",
      // Optional: Automatically open the browser when the server starts
      "serverReadyAction": {
        "pattern": "Local:\\s+(https?://\\S+)", // Common pattern for Vite/SvelteKit dev servers
        "uriFormat": "%s",
        "action": "openExternally"
      }
    }
  ],
  // Optional: Define a compound configuration to launch both with one click
  "compounds": [
    {
      "name": "Run Backend & Frontend (Concurrent)",
      "configurations": [
        "Python: Run-Flask-Backend",
        "NPM: Run-Svelte-Frontend-Dev"
      ],
      "stopAll": true // Stops all processes if one stops
    }
  ]
    }
```

2.  **Select the Python Interpreter:**
    *   Open the Command Palette (Ctrl+Shift+P or Cmd+Shift+P).
    *   Type `Python: Select Interpreter`.
    *   Choose the interpreter that points to your virtual environment (it should list `('venv': venv)` or similar and point to `backend/venv/bin/python` or `backend\venv\Scripts\python.exe`). **This is crucial!**

3.  **Run the Configurations:**
    *   Go to the "Run and Debug" view (the play button with a bug icon in the activity bar on the left).
    *   From the dropdown menu at the top, select `Python: Run-Flask-Backend` and press the green play button (F5). Wait for the backend server to start in the Terminal pane.
    *   From the dropdown menu, select `NPM: Run-Svelte-Frontend-Dev` and press the green play button (F5). Wait for the frontend server to start.
    *   **Alternatively:** Select the compound configuration `Run Backend & Frontend (Concurrent)` to start both at the same time (though the backend might not be fully ready when the frontend starts).

4.  **Access the App:** The browser should open automatically if `serverReadyAction` works, or you can manually open the URL provided by the frontend server output (e.g., `http://localhost:5173`).

#### [Shared a portion of this with the class](frontend/static/class_help.png). If this is found in other repos, they copied the .md without my permission.

<small style = "font-size: 0.8em"> ** Created to inform and help my partner set up their dev.env when beginning to work together.</small>

<small style = "font-size: 0.75em">* Information in this page has been mostly generated by Gemini per the prompt "Please create a comprehensive README to explain the project and how to create a dev build profile with the same functionality as: [pasted .xml run code from my local JetBrains IDE]"</small>