import { useRef, useState, useEffect, type ReactNode } from "react";

const CAROUSEL_THRESHOLD = 4;

interface ProductCarouselProps {
  children: ReactNode[];
  itemClassName?: string;
}

export function shouldUseCarousel(count: number): boolean {
  return count > CAROUSEL_THRESHOLD;
}

export function ProductCarousel({ children, itemClassName = "carousel-item" }: ProductCarouselProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);

  const updateControls = () => {
    const track = trackRef.current;
    if (!track) return;
    const maxScroll = track.scrollWidth - track.clientWidth;
    setCanPrev(track.scrollLeft > 8);
    setCanNext(track.scrollLeft < maxScroll - 8);
  };

  useEffect(() => {
    updateControls();
    const track = trackRef.current;
    if (!track) return;
    track.addEventListener("scroll", updateControls, { passive: true });
    window.addEventListener("resize", updateControls);
    return () => {
      track.removeEventListener("scroll", updateControls);
      window.removeEventListener("resize", updateControls);
    };
  }, [children.length]);

  const scrollByPage = (direction: -1 | 1) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: direction * track.clientWidth * 0.85, behavior: "smooth" });
  };

  return (
    <div className="carousel-shell">
      {canPrev && (
        <button type="button" className="carousel-nav carousel-nav-prev" onClick={() => scrollByPage(-1)} aria-label="Previous">
          ‹
        </button>
      )}
      <div ref={trackRef} className="carousel-track">
        {children.map((child, index) => (
          <div key={index} className={itemClassName}>
            {child}
          </div>
        ))}
      </div>
      {canNext && (
        <button type="button" className="carousel-nav carousel-nav-next" onClick={() => scrollByPage(1)} aria-label="Next">
          ›
        </button>
      )}
    </div>
  );
}

interface ProductRailProps {
  children: ReactNode[];
}

export function ProductRail({ children }: ProductRailProps) {
  if (children.length === 0) return null;

  if (shouldUseCarousel(children.length)) {
    return <ProductCarousel>{children}</ProductCarousel>;
  }

  return <div className="product-grid">{children}</div>;
}
