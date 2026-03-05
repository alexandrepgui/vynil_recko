import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';

interface Props {
  onFileSelected: (file: File) => void;
  isLoading: boolean;
}

const ACCEPTED_TYPES = ['image/jpeg', 'image/png'];

export default function ImageUpload({ onFileSelected, isLoading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = useCallback(
    (file: File) => {
      if (!ACCEPTED_TYPES.includes(file.type)) {
        alert('Please upload a JPEG or PNG image.');
        return;
      }
      setPreview(URL.createObjectURL(file));
      onFileSelected(file);
    },
    [onFileSelected],
  );

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      if (isLoading) return;
      const file = Array.from(e.clipboardData?.files ?? []).find((f) =>
        ACCEPTED_TYPES.includes(f.type),
      );
      if (file) {
        e.preventDefault();
        handleFile(file);
      }
    };
    document.addEventListener('paste', onPaste);
    return () => document.removeEventListener('paste', onPaste);
  }, [handleFile, isLoading]);

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => setIsDragging(false);

  return (
    <div
      className={`upload-zone ${isDragging ? 'dragging' : ''} ${isLoading ? 'disabled' : ''}`}
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !isLoading && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      {preview ? (
        <img src={preview} alt="Label preview" className="upload-preview" />
      ) : (
        <div className="upload-placeholder">
          <p>Drop or paste a vinyl label image here</p>
          <p className="upload-hint">or click to browse (JPEG / PNG)</p>
        </div>
      )}
    </div>
  );
}
