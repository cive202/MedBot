import { AlertTriangle } from "lucide-react";

export default function DisclaimerBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-50 text-amber-900 text-xs px-4 py-2 flex items-center gap-2">
      <AlertTriangle className="w-4 h-4 shrink-0" />
      <span>
        Health Chatbot is for informational use only and is not a substitute for professional
        medical advice, diagnosis, or treatment. Call your local emergency number for urgent care.
      </span>
    </div>
  );
}
