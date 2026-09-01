import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "AlimentIA Dashboard",
  description: "Asistente clínico para planes dietéticos",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="flex h-screen bg-[#F8FAFC] font-sans text-slate-800 overflow-hidden">
        {/* ================= SIDEBAR GLOBAL ================= */}
        <aside className="w-64 bg-[#0B1527] text-slate-300 flex flex-col justify-between flex-shrink-0">
          <div>
            <div className="p-6 flex items-center gap-3 text-white font-bold text-xl tracking-wide">
              <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center text-[#0B1527]">
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  ></path>
                </svg>
              </div>
              AlimentIA
            </div>

            {/* Navegación usando el componente Link de Next.js */}
            <nav className="mt-4 flex flex-col gap-1 px-4 text-sm font-medium">
              <Link
                href="/"
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <svg
                  className="w-5 h-5 opacity-70"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                  ></path>
                </svg>
                Resumen
              </Link>
              <Link
                href="/patients"
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <svg
                  className="w-5 h-5 opacity-70"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                  ></path>
                </svg>
                Pacientes
              </Link>
              <Link
                href="/plans"
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <svg
                  className="w-5 h-5 opacity-70"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  ></path>
                </svg>
                Planes
              </Link>
              <Link
                href="/sources"
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <svg
                  className="w-5 h-5 opacity-70"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  ></path>
                </svg>
                Fuentes
              </Link>
              <Link
                href="/alerts"
                className="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <span className="flex items-center gap-3">
                  <svg
                    className="w-5 h-5 opacity-70"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                    ></path>
                  </svg>{" "}
                  Alertas
                </span>
                <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                  5
                </span>
              </Link>
              <Link
                href="/config"
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg hover:bg-slate-800 transition-colors focus:bg-blue-600 focus:text-white"
              >
                <svg
                  className="w-5 h-5 opacity-70"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  ></path>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  ></path>
                </svg>
                Configuración
              </Link>
            </nav>
          </div>
          <div className="p-4 border-t border-slate-800">
            <div className="flex items-center gap-3 px-4 py-2">
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-xs font-bold text-white">
                N
              </div>
              <div className="text-xs">
                <p className="font-semibold text-white">Nutriólogo</p>
                <p className="text-slate-500">Sesión activa</p>
              </div>
            </div>
          </div>
        </aside>

        {/* ================= CONTENEDOR DINÁMICO ================= */}
        <main className="flex-1 flex flex-col h-full overflow-hidden relative">
          {children}
        </main>
      </body>
    </html>
  );
}
