"use client";

import { useCallback, useRef, useState } from "react";
import { motion } from "framer-motion";

interface ResumeUploaderProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function ResumeUploader({ onFileSelected, disabled }: ResumeUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      const file = e.dataTransfer.files?.[0];
      if (file && (file.type === "application/pdf" || file.name.endsWith(".pdf"))) {
        setSelectedFile(file);
        onFileSelected(file);
      }
    },
    [onFileSelected]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setSelectedFile(file);
        onFileSelected(file);
      }
    },
    [onFileSelected]
  );

  const openFilePicker = useCallback(() => {
    if (!disabled) {
      if (fileInputRef.current) fileInputRef.current.value = "";
      fileInputRef.current?.click();
    }
  }, [disabled]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  return (
    <motion.div
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={openFilePicker}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") openFilePicker(); }}
      animate={{ scale: dragActive ? 1.02 : 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 22 }}
      className={`relative rounded-xl border-2 border-dashed p-8 text-center overflow-hidden transition-colors duration-300
        ${disabled ? "pointer-events-none opacity-50" : "cursor-pointer"}
        ${
          dragActive
            ? "border-primary bg-muted/50"
            : selectedFile
            ? "border-primary bg-card"
            : "border-border bg-card hover:border-primary/50 hover:bg-muted/20"
        }`}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileInput}
        className="hidden"
        disabled={disabled}
      />

      {selectedFile ? (
        <div className="flex flex-col items-center gap-3">
          <motion.div
            initial={{ scale: 0.6, rotate: -8 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 18 }}
            className="w-16 h-16 rounded-xl bg-foreground flex items-center justify-center text-background"
          >
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </motion.div>
          <div>
            <p className="text-sm font-semibold text-foreground">{selectedFile.name}</p>
            <p className="text-xs text-muted-foreground mt-1">{formatSize(selectedFile.size)} · PDF</p>
          </div>
          <p className="text-xs text-muted-foreground font-medium">Click or drag to replace</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <motion.div
            animate={{ y: dragActive ? 0 : [0, -6, 0] }}
            transition={dragActive ? {} : { repeat: Infinity, duration: 3.5, ease: "easeInOut" }}
            className={`w-16 h-16 rounded-xl flex items-center justify-center transition-colors duration-300 ${
              dragActive ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
            }`}
          >
            <svg className="w-8 h-8"
              fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </motion.div>
          <div>
            <p className="text-sm font-medium text-foreground">
              Drop your resume here or{" "}
              <span className="font-semibold underline">browse</span>
            </p>
            <p className="text-xs text-muted-foreground mt-1">PDF only · Max 10MB</p>
          </div>
        </div>
      )}
    </motion.div>
  );
}
