import { useEffect, useRef } from "react";

type ShapeType = "line" | "z" | "square" | "dot";

interface Shape {
  x: number;
  y: number;
  size: number;
  speed: number;
  amp: number;
  phase: number;
  type: ShapeType;
  opacity: number;
  color: string;
}

const COLORS = ["127,212,198", "143,199,240", "169,162,232", "169,204,143"];

/**
 * 模板 FloatingBackground 的纯 Canvas 实现：
 * 水平漂移 + 垂直正弦，无第三方依赖；reduced-motion 下渲染单帧。
 */
export function FloatingBackground({
  shapeCount = 10,
  calm = false,
}: {
  shapeCount?: number;
  calm?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mobile = window.innerWidth < 768;
    const count = mobile ? Math.min(6, shapeCount) : shapeCount;
    const types: ShapeType[] = ["line", "z", "square", "dot"];
    let width = 0;
    let height = 0;
    let raf = 0;
    let shapes: Shape[] = [];

    const resize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    const init = () => {
      shapes = Array.from({ length: count }, (_, index) => ({
        x: Math.random() * width,
        y: Math.random() * height,
        size: 10 + Math.random() * 26,
        speed: 4 + Math.random() * 10,
        amp: 10 + Math.random() * 30,
        phase: Math.random() * Math.PI * 2,
        type: types[index % types.length],
        opacity: calm ? 0.04 : 0.05 + Math.random() * 0.08,
        color: COLORS[index % COLORS.length],
      }));
    };

    const draw = (now: number) => {
      ctx.clearRect(0, 0, width, height);
      const seconds = reduce ? 0 : now / 1000;
      for (const shape of shapes) {
        const x = ((shape.x + seconds * shape.speed) % (width + 80)) - 40;
        const y = shape.y + Math.sin(seconds * 0.5 + shape.phase) * shape.amp * 0.3;
        ctx.globalAlpha = shape.opacity;
        ctx.strokeStyle = `rgb(${shape.color})`;
        ctx.fillStyle = `rgb(${shape.color})`;
        ctx.lineWidth = 1.5;
        if (shape.type === "line") {
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + shape.size * 2.4, y);
          ctx.stroke();
        } else if (shape.type === "z") {
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + shape.size, y);
          ctx.lineTo(x, y + shape.size * 0.8);
          ctx.lineTo(x + shape.size, y + shape.size * 0.8);
          ctx.stroke();
        } else if (shape.type === "square") {
          ctx.strokeRect(x, y, shape.size * 0.7, shape.size * 0.7);
        } else {
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      if (!reduce) {
        raf = requestAnimationFrame(draw);
      }
    };

    resize();
    init();
    draw(0);
    const onResize = () => {
      resize();
      init();
      if (reduce) {
        draw(0);
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, [shapeCount, calm]);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 h-full w-full"
    />
  );
}
