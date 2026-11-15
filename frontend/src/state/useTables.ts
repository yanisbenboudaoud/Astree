/** Charge la table précalculée de la décision en cours (position ou panier) et y lit l'entrée correspondante. */
import { useEffect, useState } from 'react';
import type { DecisionUI, EntreeSimulation, Profil, TablePanier, TablePosition } from '../api/types';
import { chargerTablePanier, chargerTablePosition } from '../api/donnees';
import { entreePanier, entreePosition } from '../domaine/decision';
import { tablePanierCalibree, tablePositionCalibree } from '../domaine/calibrage';

/** Tables au seuil du Pacte de `profil` (mesuré par le Pacte vécu, #68, le cas échéant). */
export function useTables(profil: Profil, decision: DecisionUI | null) {
  const idProfil = profil.id;
  const [tablePosition, setTablePosition] = useState<TablePosition | null>(null);
  const [tablePanier, setTablePanier] = useState<TablePanier | null>(null);
  const ticker = decision?.type === 'position' ? decision.ticker : null;
  const panier = decision?.type === 'panier';

  useEffect(() => {
    let actif = true;
    if (ticker) chargerTablePosition(idProfil, ticker).then((t) => actif && setTablePosition(t));
    return () => { actif = false; };
  }, [idProfil, ticker]);

  useEffect(() => {
    let actif = true;
    if (panier) chargerTablePanier(idProfil).then((t) => actif && setTablePanier(t));
    return () => { actif = false; };
  }, [idProfil, panier]);

  const positionMesuree = tablePosition && tablePositionCalibree(tablePosition, profil);
  const panierMesure = tablePanier && tablePanierCalibree(tablePanier, profil);
  let entree: EntreeSimulation | null = null;
  if (decision?.type === 'position' && positionMesuree?.ticker === decision.ticker) entree = entreePosition(positionMesuree, decision.taille);
  if (decision?.type === 'panier' && panierMesure) entree = entreePanier(panierMesure, decision.lignes);

  return {
    tablePosition: decision?.type === 'position' && positionMesuree?.ticker === decision.ticker ? positionMesuree : null,
    tablePanier: panierMesure,
    entree,
  };
}
