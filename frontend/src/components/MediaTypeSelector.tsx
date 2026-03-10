import type { MediaType } from '../types';
import vinylIcon from '../assets/vinyl.svg';
import cdIcon from '../assets/cd.svg';

interface Props {
  onSelect: (type: MediaType) => void;
}

export default function MediaTypeSelector({ onSelect }: Props) {
  return (
    <div className="media-selector">
      <button className="media-selector-card" onClick={() => onSelect('vinyl')}>
        <img src={vinylIcon} alt="" className="media-selector-icon" />
        <div className="media-selector-text">
          <span className="media-selector-title">Vinyl</span>
          <span className="media-selector-hint">
            Take a photo of the record label — it's fine to shoot through a transparent inner sleeve
          </span>
        </div>
      </button>
      <button className="media-selector-card" onClick={() => onSelect('cd')}>
        <img src={cdIcon} alt="" className="media-selector-icon" />
        <div className="media-selector-text">
          <span className="media-selector-title">CD</span>
          <span className="media-selector-hint">
            Take a photo of the CD itself showing the printed disc face
          </span>
        </div>
      </button>
    </div>
  );
}
