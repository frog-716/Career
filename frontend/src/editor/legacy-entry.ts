import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import './legacy.css';

const w = window as typeof window & {
  html2canvas: typeof html2canvas;
  jspdf: { jsPDF: typeof jsPDF };
};
w.html2canvas = html2canvas;
w.jspdf = { jsPDF };
// @ts-ignore legacy app intentionally remains JavaScript to preserve original editor behavior.
import('./legacy-app.js');
