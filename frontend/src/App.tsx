/** Routes de l'annexe D.1. Un profil inconnu ramène à l'écran d'entrée. */
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { donneesCalibrage, profil as profilDe } from './api/donnees';
import { profilAvecCalibrage } from './domaine/calibrage';
import { useEtatProfil } from './state/store';
import { Entree } from './ecrans/Entree';
import { ConstruireMonPacte } from './ecrans/ConstruireMonPacte';
import { Portefeuille } from './ecrans/Portefeuille';
import { Calibrage } from './ecrans/Calibrage';
import { Decision } from './ecrans/Decision';
import { Tribunal } from './ecrans/Tribunal';
import { Verdict } from './ecrans/Verdict';

/** Chaque écran reçoit le profil au seuil mesuré par le Pacte vécu (#68), quand l'utilisateur l'a terminé. */
function AvecProfil({ ecran: Ecran }: { ecran: typeof Portefeuille }) {
  const { profil: id = '' } = useParams();
  const { etat } = useEtatProfil(id);
  const base = profilDe(id);
  if (!base) return <Navigate to="/" replace />;
  const profil = profilAvecCalibrage(base, donneesCalibrage(id), etat.calibrage);
  return <Ecran key={profil.id} profil={profil} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Entree />} />
      <Route path="/construire" element={<ConstruireMonPacte />} />
      <Route path="/:profil/portefeuille" element={<AvecProfil ecran={Portefeuille} />} />
      <Route path="/:profil/pacte-vecu" element={<AvecProfil ecran={Calibrage} />} />
      <Route path="/:profil/decision" element={<AvecProfil ecran={Decision} />} />
      <Route path="/:profil/tribunal" element={<AvecProfil ecran={Tribunal} />} />
      <Route path="/:profil/verdict" element={<AvecProfil ecran={Verdict} />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
