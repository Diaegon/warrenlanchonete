"use client";

interface AlertBannerProps {
  message: string;
}

export default function AlertBanner({ message }: AlertBannerProps) {
  return (
    <div className="flex items-start gap-3 bg-nubank-purple/10 border border-nubank-purple/40 rounded-lg px-4 py-3">
      <span className="text-nubank-purple text-lg leading-none mt-0.5 select-none">
        ⚡
      </span>
      <p className="text-nubank-text text-sm leading-relaxed">{message}</p>
    </div>
  );
}
