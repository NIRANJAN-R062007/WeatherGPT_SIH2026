// The white city chip (pin, "City, Region", chevron) and the city picker it
// opens, plus a "use my location" row: /ask and /warnings take a city, not
// coordinates, so location means the nearest registered city
// (mobile/lib/components/common.dart's showCityPicker).
import { useState } from 'react';
import { CITIES, nearestCity } from '../data/cities';
import { useUiPrefs } from '../state/UiPrefsContext';
import { Icon, Sheet, Spinner } from './ui';

function locate(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('This browser has no location support. Pick a city instead.'));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, (err) =>
      reject(
        new Error(
          err.code === err.PERMISSION_DENIED
            ? 'Location permission denied. Pick a city manually instead.'
            : "Couldn't get your location. Pick a city manually instead.",
        ),
      ),
      { enableHighAccuracy: false, timeout: 15_000 },
    );
  });
}

export function CityPickerSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { city, setCity } = useUiPrefs();
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);

  const useMyLocation = async () => {
    setLocating(true);
    setLocateError(null);
    try {
      const pos = await locate();
      setCity(nearestCity(pos.coords.latitude, pos.coords.longitude).key);
      onClose();
    } catch (err) {
      setLocateError(err instanceof Error ? err.message : String(err));
    } finally {
      setLocating(false);
    }
  };

  const row = 'w-full flex items-center gap-2 px-3 py-3 rounded-lg text-left transition-colors';
  return (
    <Sheet open={open} onClose={onClose} title="Choose a city">
      <button type="button" disabled={locating} onClick={useMyLocation} className={`${row} hover:bg-tint`}>
        <Icon name="my_location" size={18} className="text-on-surface-variant" />
        <span className="flex-1">
          <span className="block font-label-md text-label-md text-on-surface">Use my location</span>
          <span className="block font-body-sm text-body-sm text-on-surface-variant">
            {locateError ?? 'Nearest supported city'}
          </span>
        </span>
        {locating && <Spinner />}
      </button>
      <div className="my-1 mx-3 h-px bg-outline-variant" />
      {CITIES.map((c) => {
        const active = c.key === city;
        return (
          <button
            key={c.key}
            type="button"
            onClick={() => {
              setCity(c.key);
              onClose();
            }}
            className={`${row} ${active ? 'bg-primary-container/10' : 'hover:bg-tint'}`}
          >
            <Icon
              name={active ? 'radio_button_checked' : 'location_on'}
              size={18}
              className={active ? 'text-primary' : 'text-on-surface-variant'}
            />
            <span
              className={`font-label-md text-label-md ${active ? 'text-primary font-semibold' : 'text-on-surface'}`}
            >
              {c.name}, {c.region}
            </span>
          </button>
        );
      })}
    </Sheet>
  );
}

export function CityPill() {
  const { cityInfo } = useUiPrefs();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 pl-3.5 pr-3 py-2 rounded-full bg-card shadow-card hover:brightness-[0.98]"
      >
        <Icon name="location_on" size={18} fill className="text-primary" />
        <span className="max-w-[220px] truncate font-label-md text-label-md font-semibold text-ink">
          {cityInfo.name}, {cityInfo.region}
        </span>
        <Icon name="keyboard_arrow_down" size={18} className="text-ink-muted" />
      </button>
      <CityPickerSheet open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/** The composers' "IF UNSPECIFIED, ASSUME [city] · LANG XX" row. The city is
 *  only a hint — /ask's NLU uses a city named in the question first. */
export function CityHintRow() {
  const { cityInfo, lang } = useUiPrefs();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-1.5 px-1 font-citation-mono text-citation-mono text-on-surface-variant">
      <Icon name="my_location" size={14} />
      <span>IF UNSPECIFIED, ASSUME</span>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center rounded px-1.5 py-1 bg-surface-container-low text-on-surface font-label-md text-label-md hover:bg-surface-container"
      >
        {cityInfo.name}
        <Icon name="expand_more" size={16} className="text-on-surface-variant" />
      </button>
      <span className="text-outline">· LANG {lang.toUpperCase()}</span>
      <CityPickerSheet open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
