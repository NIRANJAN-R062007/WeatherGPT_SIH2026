import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

export default function Layout() {
  return (
    <>
      <Sidebar />
      <div className="pl-64 flex flex-col min-h-screen">
        <Topbar />
        <main className="flex-1 pt-16 bg-surface w-full px-space-xl py-space-lg">
          <Outlet />
        </main>
      </div>
    </>
  );
}
