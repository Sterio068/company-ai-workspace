const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("node:path");
const { registerUpdateIpc } = require("./updater.cjs");

let mainWindow = null;

function appUrl() {
  return process.env.COMPANY_AI_DESKTOP_URL || "http://localhost";
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 720,
    title: "企業 AI 工作台",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadURL(appUrl());
}

app.whenReady().then(() => {
  registerUpdateIpc({ app, ipcMain, getWindow: () => mainWindow });
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
