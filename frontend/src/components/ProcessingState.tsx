"use client";

import { motion } from "framer-motion";

interface ProcessingStateProps {
  status: string;
  fileName: string;
}

const STEPS = [
  { key: "pending", label: "Uploading", icon: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" },
  { key: "processing", label: "Parsing Resume", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { key: "embedding", label: "Generating Embeddings", icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" },
  { key: "ready", label: "Ready!", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" },
];

function getStepIndex(status: string): number {
  if (status === "ready") return 3;
  if (status === "embedding") return 2;
  if (status === "processing") return 1;
  return 0;
}

export default function ProcessingState({ status, fileName }: ProcessingStateProps) {
  const currentStep = getStepIndex(status);
  const done = status === "ready";

  return (
    <div className="flex flex-col items-center justify-center py-16 px-8">
      <div className="relative mb-8">
        <motion.div
          animate={!done ? { scale: [1, 1.06, 1] } : { scale: 1 }}
          transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          className={`w-24 h-24 rounded-3xl flex items-center justify-center border ${
            done ? "bg-emerald-500/15 border-emerald-400/30" : "bg-violet-500/12 border-violet-400/25 ring-accent"
          }`}
        >
          <motion.svg
            key={currentStep}
            initial={{ scale: 0.8, opacity: 0, rotate: -10 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className={`w-12 h-12 ${done ? "text-emerald-400" : "text-violet-300"}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={STEPS[currentStep].icon} />
          </motion.svg>
        </motion.div>
        {!done && <div className="absolute inset-0 rounded-3xl border-2 border-violet-400/30 animate-ping pointer-events-none" />}
      </div>

      <h3 className="text-lg font-bold text-fg mb-2">{done ? "Resume Processed!" : "Processing Your Resume"}</h3>
      <p className="text-sm text-fg/40 mb-8">{fileName}</p>

      <div className="flex items-center gap-2 w-full max-w-md">
        {STEPS.map((step, i) => (
          <div key={step.key} className="flex-1 flex items-center gap-2">
            <div className="flex-1 flex flex-col items-center">
              <motion.div
                animate={{ scale: i === currentStep ? 1.15 : 1 }}
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors duration-500 ${
                  i < currentStep ? "bg-emerald-500 text-white"
                  : i === currentStep ? "bg-accent text-white shadow-[0_0_18px_rgba(139,92,246,0.6)]"
                  : "bg-fg/5 text-fg/25"
                }`}
              >
                {i < currentStep ? (
                  <motion.svg initial={{ scale: 0 }} animate={{ scale: 1 }} className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </motion.svg>
                ) : i + 1}
              </motion.div>
              <p className={`text-[10px] mt-1.5 text-center transition-colors duration-500 ${i <= currentStep ? "text-fg/60" : "text-fg/20"}`}>
                {step.label}
              </p>
            </div>
            {i < STEPS.length - 1 && (
              <div className="w-full h-0.5 bg-fg/5 rounded -mt-5 relative overflow-hidden">
                <motion.div
                  initial={{ width: "0%" }}
                  animate={{ width: i < currentStep ? "100%" : i === currentStep ? "50%" : "0%" }}
                  transition={{ duration: 0.8, ease: "easeInOut" }}
                  className="absolute left-0 top-0 bottom-0 bg-gradient-to-r from-emerald-500 to-violet-500"
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
