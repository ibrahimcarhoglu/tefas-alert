"use client";

interface Props {
  children: React.ReactNode;
  className?: string;
}

export default function Badge({ children, className = "" }: Props) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[0.7rem] font-bold ${className}`}
    >
      {children}
    </span>
  );
}
