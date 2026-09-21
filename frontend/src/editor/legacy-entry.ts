import './legacy.css';
import { requestWithSession } from '../local-session';

declare global {
  interface Window {
    __careerSessionRequest__?: typeof requestWithSession;
  }
}

window.__careerSessionRequest__ = requestWithSession;

// @ts-ignore legacy app intentionally remains JavaScript to preserve original editor behavior.
import('./legacy-app.js');
