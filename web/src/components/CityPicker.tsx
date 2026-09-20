import type { City, Lang } from '../api/types';

interface Props {
  cities: City[];
  value: string;
  onChange: (key: string) => void;
  lang: Lang;
  legend: string;
  legendHidden?: boolean;
  name: string;
}

/** Segmented city selector — real radios visually hidden behind labels. */
export function CityPicker({ cities, value, onChange, lang, legend, legendHidden, name }: Props) {
  return (
    <fieldset>
      <legend
        className={
          legendHidden
            ? 'sr-only'
            : 'mb-2 font-mono text-xs uppercase tracking-[0.18em] text-ink-faint'
        }
      >
        {legend}
      </legend>
      <div className="flex flex-wrap gap-2">
        {cities.map((city) => (
          <div key={city.key}>
            <input
              type="radio"
              id={`${name}-${city.key}`}
              name={name}
              value={city.key}
              checked={value === city.key}
              onChange={() => onChange(city.key)}
              className="peer sr-only"
            />
            <label
              htmlFor={`${name}-${city.key}`}
              lang={lang}
              className="block cursor-pointer rounded-sm border border-line px-3 py-1.5 text-sm text-ink-dim transition-colors hover:bg-paper-dim peer-checked:border-monsoon peer-checked:bg-monsoon peer-checked:text-paper-hi peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-monsoon active:scale-[0.98]"
            >
              {city.names[lang] ?? city.names.en}
            </label>
          </div>
        ))}
      </div>
    </fieldset>
  );
}
