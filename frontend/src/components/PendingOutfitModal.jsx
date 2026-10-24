import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter } from "@/components/ui/alert-dialog";

export default function PendingOutfitModal({ draft, onResume, onDiscard }) {
  const n = (draft?.selectedItems?.length || 0) + (draft?.single?.garment_path ? 1 : 0);
  return (
    <AlertDialog open={!!draft}>
      <AlertDialogContent className="rounded-none" data-testid="pending-outfit-modal">
        <AlertDialogHeader>
          <div className="label-caps">Atelier Fit</div>
          <AlertDialogTitle className="font-serif text-2xl tracking-tight">Hai un outfit in sospeso, vuoi riprendere?</AlertDialogTitle>
          <AlertDialogDescription data-testid="pending-outfit-count">
            {n === 1 ? "1 capo selezionato" : `${n} capi selezionati`} con il tuo Avatar. Resta disponibile per 5 minuti.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="gap-2">
          <button onClick={onDiscard} className="border hairline px-5 py-3 label-caps hover:border-[#0A0A0A] transition-colors" data-testid="pending-outfit-discard">
            Scarta
          </button>
          <button onClick={onResume} className="btn-primary justify-center" data-testid="pending-outfit-resume">
            Riprendi
          </button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
