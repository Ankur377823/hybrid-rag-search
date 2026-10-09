/**
 * Central state store with subscription listeners.
 */

import { getToken, getUser, setToken, setUser } from './api.js';

class StateStore {
  constructor() {
    this.token = getToken();
    this.user = getUser();
    this.activeTab = 'documents'; // 'documents' | 'query'
    this.documents = [];
    this.health = { status: 'checking', database: 'detecting...', chunks: 0 };
    this.telemetryLogs = [
      { time: this._now(), text: 'INCOMING CLIENT CONNECTION ESTABLISHED ...' },
      { time: this._now(), text: 'SECURITY GATE INITIALIZED [JWT: RS256/HS256]' },
      { time: this._now(), text: 'NEON POSTGRESQL DRIVER POOL READY ...' },
    ];
    this.listeners = [];
  }

  _now() {
    return new Date().toTimeString().split(' ')[0];
  }

  addLog(msg) {
    this.telemetryLogs.push({ time: this._now(), text: msg });
    if (this.telemetryLogs.length > 30) this.telemetryLogs.shift();
    this.notify();
  }

  setAuth(token, user) {
    this.token = token;
    this.user = user;
    setToken(token);
    setUser(user);
    this.addLog(user ? `SESSION AUTHENTICATED: ${user.email}` : 'USER SIGNED OUT');
    this.notify();
  }

  setDocuments(docs) {
    this.documents = docs || [];
    this.notify();
  }

  setActiveTab(tab) {
    this.activeTab = tab;
    this.notify();
  }

  setHealth(health) {
    this.health = health;
    this.notify();
  }

  subscribe(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter((cb) => cb !== callback);
    };
  }

  notify() {
    for (const cb of this.listeners) {
      cb(this);
    }
  }
}

export const store = new StateStore();
