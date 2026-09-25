export default function Topbar({ city = 'Mumbai, Maharashtra' }: { city?: string }) {
  return (
    <header className="fixed top-0 left-64 right-0 h-16 bg-surface-container-lowest/90 backdrop-blur-xl z-40 flex items-center justify-between px-space-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)]">
      <div className="flex items-center gap-space-md">
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-container-low text-on-surface font-label-md text-label-md cursor-pointer hover:bg-surface-container transition-colors">
          <span className="material-symbols-outlined text-primary text-[18px]">location_on</span>
          <span className="font-medium">{city}</span>
          <span className="material-symbols-outlined text-on-surface-variant text-[16px]">expand_more</span>
        </div>
      </div>
      <div className="flex items-center gap-space-md">
        <button
          type="button"
          className="relative p-2 rounded-full hover:bg-surface-container transition-colors text-on-surface-variant"
        >
          <span className="material-symbols-outlined text-[22px]">notifications</span>
        </button>
      </div>
    </header>
  );
}
