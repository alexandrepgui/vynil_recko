import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import type { MediaType } from '../types';

interface Props {
  onFileSelected: (file: File) => void;
  onClear?: () => void;
  isLoading: boolean;
  mediaType?: MediaType;
}

const ACCEPTED_TYPES = ['image/jpeg', 'image/png'];

export default function ImageUpload({ onFileSelected, onClear, isLoading, mediaType = 'vinyl' }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const stageFile = useCallback((file: File) => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      alert('Please upload a JPEG or PNG image.');
      return;
    }
    setStagedFile(file);
    setPreview(URL.createObjectURL(file));
  }, []);

  const handleClear = useCallback(() => {
    setStagedFile(null);
    setPreview(null);
    onClear?.();
  }, [onClear]);

  const handleSubmit = useCallback(() => {
    if (stagedFile) onFileSelected(stagedFile);
  }, [stagedFile, onFileSelected]);

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) stageFile(file);
    },
    [stageFile],
  );

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      if (isLoading) return;
      const file = Array.from(e.clipboardData?.files ?? []).find((f) =>
        ACCEPTED_TYPES.includes(f.type),
      );
      if (file) {
        e.preventDefault();
        stageFile(file);
      }
    };
    document.addEventListener('paste', onPaste);
    return () => document.removeEventListener('paste', onPaste);
  }, [stageFile, isLoading]);

  const onDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => setIsDragging(false);

  return (
    <div>
      <div
        className={`upload-zone ${isDragging ? 'dragging' : ''} ${isLoading ? 'disabled' : ''}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => !isLoading && !stagedFile && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) stageFile(file);
          }}
        />

        {preview ? (
          <img src={preview} alt="Label preview" className="upload-preview" />
        ) : (
          <div className="upload-placeholder">
            <p>Drop or paste a {mediaType === 'cd' ? 'CD' : 'vinyl label'} image here</p>
            <p className="upload-hint">or click to browse (JPEG / PNG)</p>
          </div>
        )}
      </div>

      {stagedFile && !isLoading && (
        <div className="upload-actions">
          <button className="btn btn-submit" onClick={handleSubmit}>
            Search
          </button>
          <button className="btn btn-clear" onClick={handleClear}>
            Clear
          </button>
        </div>
      )}
    </div>
  );
}
