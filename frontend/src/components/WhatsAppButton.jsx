const NUMBER = process.env.REACT_APP_WHATSAPP_NUMBER;
const HREF = `https://wa.me/${NUMBER}?text=${encodeURIComponent("Ciao My Atelier")}`;

// Official WhatsApp floating button, fixed bottom-right on every page.
export default function WhatsAppButton() {
  if (!NUMBER) return null;
  return (
    <a href={HREF} target="_blank" rel="noopener noreferrer" aria-label="Scrivici su WhatsApp" title="Scrivici su WhatsApp"
      className="fixed bottom-5 right-5 md:bottom-6 md:right-6 z-[60] h-14 w-14 rounded-full bg-[#25D366] shadow-lg shadow-black/20 flex items-center justify-center transition-transform duration-200 hover:scale-110 active:scale-95"
      data-testid="whatsapp-float-btn">
      <svg viewBox="0 0 32 32" width="30" height="30" fill="#FFFFFF" aria-hidden="true">
        <path d="M16.004 3C8.832 3 3 8.83 3 16c0 2.29.6 4.53 1.74 6.5L3 29l6.68-1.75A12.95 12.95 0 0 0 16.004 29C23.17 29 29 23.17 29 16S23.17 3 16.004 3zm0 23.62c-1.95 0-3.86-.52-5.53-1.51l-.4-.24-3.96 1.04 1.06-3.86-.26-.4A10.58 10.58 0 0 1 5.38 16c0-5.86 4.77-10.62 10.63-10.62 5.85 0 10.61 4.76 10.61 10.62 0 5.86-4.76 10.62-10.62 10.62zm5.83-7.95c-.32-.16-1.89-.93-2.18-1.04-.29-.11-.5-.16-.72.16-.21.32-.82 1.04-1 1.25-.19.21-.37.24-.69.08-.32-.16-1.35-.5-2.57-1.59-.95-.85-1.59-1.9-1.78-2.22-.19-.32-.02-.49.14-.65.14-.14.32-.37.48-.56.16-.19.21-.32.32-.53.11-.21.05-.4-.03-.56-.08-.16-.72-1.73-.98-2.37-.26-.62-.52-.54-.72-.55h-.61c-.21 0-.56.08-.85.4-.29.32-1.12 1.09-1.12 2.66 0 1.57 1.14 3.09 1.3 3.3.16.21 2.25 3.43 5.44 4.81.76.33 1.35.52 1.81.67.76.24 1.46.21 2.01.13.61-.09 1.89-.77 2.15-1.52.27-.75.27-1.39.19-1.52-.08-.13-.29-.21-.61-.37z" />
      </svg>
    </a>
  );
}
