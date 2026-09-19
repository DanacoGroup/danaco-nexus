'use strict';
// Preload lokalnych stron aplikacji (pasek panelu, języczek, ustawienia, okno zgody):
// wąskie API z listą dozwolonych kanałów IPC.

const { contextBridge, ipcRenderer } = require('electron');

const INVOKE = new Set([
  'confirm:get',
  'confirm:answer',
  'settings:get',
  'settings:save',
  'device:connect',
  'device:set-key',
  'device:clear',
  'panel:action',
  'tab:hover',
]);
const EVENTS = new Set(['panel:state', 'agent:status']);

contextBridge.exposeInMainWorld('nexus', {
  invoke(channel, ...args) {
    if (!INVOKE.has(channel)) return Promise.reject(new Error(`Niedozwolony kanał: ${channel}`));
    return ipcRenderer.invoke(channel, ...args);
  },
  on(channel, callback) {
    if (!EVENTS.has(channel)) return;
    ipcRenderer.on(channel, (_event, payload) => callback(payload));
  },
});
