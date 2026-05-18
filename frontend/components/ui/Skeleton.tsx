"use client";

interface Props {
  count?: number;
  className?: string;
}

export default function Skeleton({ count = 3, className = "h-12 w-full" }: Props) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={`skeleton ${className}`} />
      ))}
    </div>
  );
}
