"use client";

interface GradeDisplayProps {
  grade: string;
}

function gradeColorClass(grade: string): string {
  const letter = grade.charAt(0).toUpperCase();
  if (letter === "A") return "text-green-400";
  if (letter === "B") return "text-yellow-400";
  if (letter === "C") return "text-orange-400";
  return "text-red-400";
}

function gradeRingClass(grade: string): string {
  const letter = grade.charAt(0).toUpperCase();
  if (letter === "A") return "ring-green-400";
  if (letter === "B") return "ring-yellow-400";
  if (letter === "C") return "ring-orange-400";
  return "ring-red-400";
}

function gradeLabel(grade: string): string {
  const letter = grade.charAt(0).toUpperCase();
  if (letter === "A") return "Portfólio excelente";
  if (letter === "B") return "Portfólio razoável";
  if (letter === "C") return "Precisa melhorar";
  return "Portfólio preocupante";
}

export default function GradeDisplay({ grade }: GradeDisplayProps) {
  const colorClass = gradeColorClass(grade);
  const ringClass = gradeRingClass(grade);

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className={`w-28 h-28 rounded-full ring-4 ${ringClass} bg-nubank-card flex items-center justify-center`}
      >
        <span className={`text-6xl font-extrabold ${colorClass} leading-none`}>
          {grade}
        </span>
      </div>
      <span className="text-nubank-muted text-sm font-medium">
        {gradeLabel(grade)}
      </span>
    </div>
  );
}
