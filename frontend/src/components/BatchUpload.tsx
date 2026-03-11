import { useCallback, useRef, useState, type DragEvent } from 'react';
import { uploadBatch } from '../api';
import type { MediaType } from '../types';

interface Props {
  onBatchCreated: (batchId: string, totalImages: number) => void;
  mediaType?: MediaType;
}

export default function BatchUpload({ onBatchCreated, mediaType = 'vinyl' }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith('.zip')) {
        setError('That doesn\'t look like a .zip file. Try a .zip with JPEG or PNG images inside.');
        return;
      }
      const MAX_ZIP_SIZE = 750 * 1024 * 1024; // 750 MB
      if (file.size > MAX_ZIP_SIZE) {
        alert('ZIP file must be under 750 MB.');
        return;
      }
      setError(null);
      setIsUploading(true);

      try {
        const { batch_id, total_images } = await uploadBatch(file, mediaType);
        onBatchCreated(batch_id, total_images);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Upload didn\'t work. Want to try again?');
      } finally {
        setIsUploading(false);
      }
    },
    [onBatchCreated, mediaType],
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

  return (
    <div
      className={`upload-zone ${isDragging ? 'dragging' : ''} ${isUploading ? 'disabled' : ''}`}
      onDrop={onDrop}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onClick={() => !isUploading && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".zip"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />

      <div className="upload-placeholder">
        {isUploading ? (
          <p>Uploading...</p>
        ) : (
          <>
            <p>Drop a <strong>.zip</strong> file here</p>
            <p className="upload-hint">or click to browse</p>
            <p className="upload-hint">
              Must contain {mediaType === 'cd' ? 'CD' : 'vinyl label'} photos (JPEG or PNG)
            </p>
          </>
        )}
      </div>

      {error && <p className="batch-upload-error">{error}</p>}
    </div>
  );
}
