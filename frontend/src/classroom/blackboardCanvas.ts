import { BlackboardData } from '../types';

/**
 * Creates and updates a 2D HTML5 canvas that serves as the dynamic texture
 * for the 3D classroom blackboard in Three.js.
 */
export function createBlackboardCanvas(): {
  canvas: HTMLCanvasElement;
  updateContent: (data: BlackboardData) => void;
} {
  const canvas = document.createElement('canvas');
  canvas.width = 1280;
  canvas.height = 640;
  const ctx = canvas.getContext('2d')!;

  function drawChalkboard(data: BlackboardData) {
    const w = canvas.width;
    const h = canvas.height;

    // 1. Dark blackboard base with subtle vignette
    const bgGrad = ctx.createRadialGradient(w / 2, h / 2, 100, w / 2, h / 2, w * 0.7);
    bgGrad.addColorStop(0, '#1c3329'); // rich dark chalkboard green
    bgGrad.addColorStop(1, '#0e1d17');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);

    // 2. Chalk dust streaks & eraser marks
    ctx.fillStyle = 'rgba(255, 255, 255, 0.035)';
    for (let i = 0; i < 40; i++) {
      const sx = Math.random() * w;
      const sy = Math.random() * h;
      const sw = 60 + Math.random() * 180;
      const sh = 10 + Math.random() * 25;
      ctx.fillRect(sx, sy, sw, sh);
    }

    // Border chalk line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.lineWidth = 4;
    ctx.strokeRect(20, 20, w - 40, h - 40);

    // 3. Header title in warm chalk
    ctx.fillStyle = '#fef08a'; // pale yellow chalk
    ctx.font = 'bold 36px "Courier New", monospace, sans-serif';
    ctx.textBaseline = 'top';
    ctx.fillText(`✎  ${data.title.toUpperCase()}`, 50, 45);

    // Chalk underline
    ctx.strokeStyle = '#fef08a';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(50, 92);
    ctx.lineTo(w - 50, 92);
    ctx.stroke();

    // 4. Split Layout: Left side for Bullet points, Right side for Diagram
    const leftWidth = w * 0.58;

    // Bullet points
    ctx.font = '24px "Courier New", monospace, sans-serif';
    ctx.fillStyle = '#ffffff';
    let currentY = 120;

    (data.bullets || []).forEach((bullet, idx) => {
      ctx.fillStyle = idx === 0 ? '#67e8f9' : '#f8fafc'; // Accent color for primary formula/law

      // Wrap text if long
      const words = bullet.split(' ');
      let line = '• ';
      for (let n = 0; n < words.length; n++) {
        const testLine = line + words[n] + ' ';
        const metrics = ctx.measureText(testLine);
        if (metrics.width > leftWidth - 60 && n > 0) {
          ctx.fillText(line, 55, currentY);
          line = '    ' + words[n] + ' ';
          currentY += 34;
        } else {
          line = testLine;
        }
      }
      ctx.fillText(line, 55, currentY);
      currentY += 46;
    });

    // 5. Diagram area on the right side
    const diagX = leftWidth + 30;
    const diagY = 120;
    const diagW = w - diagX - 50;
    const diagH = h - diagY - 80;

    // Diagram Box
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.4)';
    ctx.setLineDash([8, 6]);
    ctx.lineWidth = 2;
    ctx.strokeRect(diagX, diagY, diagW, diagH);
    ctx.setLineDash([]);

    // Diagram Title
    ctx.fillStyle = '#94a3b8';
    ctx.font = 'bold 18px "Courier New", monospace, sans-serif';
    ctx.fillText('DIAGRAM / MODEL', diagX + 15, diagY + 15);

    // Render diagram based on type
    drawDiagram(ctx, data.diagramType, diagX, diagY, diagW, diagH);

    // Diagram Annotation Note
    if (data.diagramNote) {
      ctx.fillStyle = '#fde047';
      ctx.font = 'italic 19px "Courier New", monospace, sans-serif';
      ctx.fillText(`Note: ${data.diagramNote}`, diagX + 10, diagY + diagH - 25);
    }

    // Chalk footer
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.font = '16px "Courier New", monospace, sans-serif';
    ctx.fillText('Classroom Interactive Board • AI Tutor Bob', 55, h - 50);
  }

  function drawDiagram(
    context: CanvasRenderingContext2D,
    type: string,
    x: number,
    y: number,
    w: number,
    h: number
  ) {
    const cx = x + w / 2;
    const cy = y + h / 2 - 10;

    context.strokeStyle = '#ffffff';
    context.lineWidth = 3;

    if (type === 'free_body' || type.includes('free') || type.includes('force')) {
      // Free body diagram (Block with force vectors)
      const bw = 80;
      const bh = 50;
      context.strokeRect(cx - bw / 2, cy - bh / 2, bw, bh);
      context.fillStyle = 'rgba(255, 255, 255, 0.15)';
      context.fillRect(cx - bw / 2, cy - bh / 2, bw, bh);

      // Mass label
      context.fillStyle = '#ffffff';
      context.font = 'bold 20px "Courier New", monospace';
      context.fillText('m', cx - 6, cy + 6);

      // Arrow Down (Fg)
      drawArrow(context, cx, cy + bh / 2, cx, cy + bh / 2 + 65, '#f87171', 'F_g = mg');
      // Arrow Up (Fn)
      drawArrow(context, cx, cy - bh / 2, cx, cy - bh / 2 - 65, '#4ade80', 'F_N');
      // Arrow Right (F_applied)
      drawArrow(context, cx + bw / 2, cy, cx + bw / 2 + 70, cy, '#60a5fa', 'F_net = ma');
    } else if (type === 'trajectory' || type.includes('parabol') || type.includes('curve')) {
      // Parabolic trajectory
      context.beginPath();
      context.moveTo(x + 30, y + h - 50);
      context.quadraticCurveTo(cx, y + 50, x + w - 30, y + h - 50);
      context.strokeStyle = '#38bdf8';
      context.stroke();

      // Launch vector
      drawArrow(context, x + 30, y + h - 50, x + 85, y + h - 105, '#facc15', 'v0');

      // Apex point
      context.fillStyle = '#f43f5e';
      context.beginPath();
      context.arc(cx, y + 80, 6, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = '#ffffff';
      context.font = '16px "Courier New", monospace';
      context.fillText('Apex (vy = 0)', cx - 45, y + 65);
    } else if (type === 'energy_graph' || type.includes('graph')) {
      // Coordinate axes
      context.strokeStyle = '#94a3b8';
      context.beginPath();
      context.moveTo(x + 40, y + 40);
      context.lineTo(x + 40, y + h - 50);
      context.lineTo(x + w - 30, y + h - 50);
      context.stroke();

      // Kinetic energy (rising)
      context.beginPath();
      context.moveTo(x + 40, y + h - 60);
      context.lineTo(x + w - 40, y + 60);
      context.strokeStyle = '#22c55e';
      context.stroke();

      // Potential energy (falling)
      context.beginPath();
      context.moveTo(x + 40, y + 60);
      context.lineTo(x + w - 40, y + h - 60);
      context.strokeStyle = '#eab308';
      context.stroke();

      context.fillStyle = '#22c55e';
      context.font = '16px "Courier New", monospace';
      context.fillText('KE', x + w - 30, y + 65);
      context.fillStyle = '#eab308';
      context.fillText('PE', x + w - 30, y + h - 55);
    } else {
      // Conceptual Flowchart boxes
      const boxW = 100;
      const boxH = 40;

      // Box 1
      context.strokeStyle = '#38bdf8';
      context.strokeRect(cx - boxW / 2, cy - 70, boxW, boxH);
      context.fillStyle = '#ffffff';
      context.font = '16px "Courier New", monospace';
      context.fillText('Concept', cx - 30, cy - 45);

      // Arrow down
      drawArrow(context, cx, cy - 30, cx, cy + 10, '#fde047');

      // Box 2
      context.strokeStyle = '#4ade80';
      context.strokeRect(cx - boxW / 2, cy + 10, boxW, boxH);
      context.fillStyle = '#ffffff';
      context.fillText('Equation', cx - 32, cy + 35);
    }
  }

  function drawArrow(
    ctx2: CanvasRenderingContext2D,
    fromX: number,
    fromY: number,
    toX: number,
    toY: number,
    color: string,
    label?: string
  ) {
    ctx2.save();
    ctx2.strokeStyle = color;
    ctx2.fillStyle = color;
    ctx2.lineWidth = 3;
    ctx2.beginPath();
    ctx2.moveTo(fromX, fromY);
    ctx2.lineTo(toX, toY);
    ctx2.stroke();

    const angle = Math.atan2(toY - fromY, toX - fromX);
    const headLen = 12;
    ctx2.beginPath();
    ctx2.moveTo(toX, toY);
    ctx2.lineTo(toX - headLen * Math.cos(angle - Math.PI / 6), toY - headLen * Math.sin(angle - Math.PI / 6));
    ctx2.lineTo(toX - headLen * Math.cos(angle + Math.PI / 6), toY - headLen * Math.sin(angle + Math.PI / 6));
    ctx2.closePath();
    ctx2.fill();

    if (label) {
      ctx2.fillStyle = color;
      ctx2.font = 'bold 16px "Courier New", monospace';
      ctx2.fillText(label, toX + 8, toY + 4);
    }
    ctx2.restore();
  }

  return {
    canvas,
    updateContent: drawChalkboard,
  };
}
