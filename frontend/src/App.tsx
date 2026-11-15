/** Routes de l'annexe D.1. Un profil inconnu ramène à l'écran d'entrée. */
import { Navigate, Route, Routes, useParams } from 'react-router-dom';
import { profil as profilDe } from './api/donnees';
import { Entree } from './ecrans/Entree';
import { Portefeuille } from './ecrans/Portefeuille';
import { Decision } from './ecrans/Decision';
import { Tribunal } from './ecrans/Tribunal';
import { Verdict } from './ecrans/Verdict';

function AvecProfil({ ecran: Ecran }: { ecran: typeof Portefeuille }) {
  const { profil: id = '' } = useParams();
  const profil = profilDe(id);
  if (!profil) return <Navigate to="/" replace />;
  return <Ecran key={profil.id} profil={profil} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Entree />} />
      <Route path="/:profil/portefeuille" element={<AvecProfil ecran={Portefeuille} />} />
      <Route path="/:profil/decision" element={<AvecProfil ecran={Decision} />} />
      <Route path="/:profil/tribunal" element={<AvecProfil ecran={Tribunal} />} />
      <Route path="/:profil/verdict" element={<AvecProfil ecran={Verdict} />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
