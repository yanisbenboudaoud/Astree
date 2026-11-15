/** Charge la table précalculée de la décision en cours (position ou panier) et y lit l'entrée correspondante. */
import { useEffect, useState } from 'react';
import type { DecisionUI, EntreeSimulation, TablePanier, TablePosition } from '../api/types';
import { chargerTablePanier, chargerTablePosition } from '../api/donnees';
import { entreePanier, entreePosition } from '../domaine/decision';

export function useTables(idProfil: string, decision: DecisionUI | null) {
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

  let entree: EntreeSimulation | null = null;
  if (decision?.type === 'position' && tablePosition?.ticker === decision.ticker) entree = entreePosition(tablePosition, decision.taille);
  if (decision?.type === 'panier' && tablePanier) entree = entreePanier(tablePanier, decision.lignes);

  return {
    tablePosition: decision?.type === 'position' && tablePosition?.ticker === decision.ticker ? tablePosition : null,
    tablePanier,
    entree,
  };
}
