/** Lecture du Pacte d'un profil : numéros de règles, statuts, règle clé. Aucune règle n'est codée en dur. */
import categories from '../data/generated/categories.json';
import type { StatutContrat } from '../api/contrat';
import type { Profil, ReglePacte, Statut, Titre } from '../api/types';
import { LIBELLES } from '../api/donnees';
import { part, pourcent } from '../lib/format';

export const TYPES_CALCULABLES = ['pire_baisse_max', 'plafond'] as const;

export function statutUi(statut: StatutContrat): Statut {
  if (statut === 'violation') return 'Violation';
  if (statut === 'a_verifier') return 'À vérifier';
  return 'Conforme';
}

const GRAVITE: Record<Statut, number> = { Violation: 0, 'À vérifier': 1, Conforme: 2 };

export function parGravite<T extends { statut: Statut }>(elements: T[]): T[] {
  return [...elements].sort((a, b) => GRAVITE[a.statut] - GRAVITE[b.statut]);
}

export function pireStatut(statuts: Statut[]): Statut {
  return statuts.reduce<Statut>((pire, s) => (GRAVITE[s] < GRAVITE[pire] ? s : pire), 'Conforme');
}

/** Numéro de la règle dans le Pacte (§1 pour la première), ou undefined si ce n'est pas une règle du Pacte. */
export function paragraphe(regles: { id: string }[], idRegle: string): number | undefined {
  const i = regles.findIndex((r) => r.id === idRegle);
  return i >= 0 ? i + 1 : undefined;
}

export function estCalculable(regle: { type: string }): boolean {
  return (TYPES_CALCULABLES as readonly string[]).includes(regle.type);
}

export function libelleCategories(ids: string[]): string {
  const noms = ids.map((id) => (categories as Record<string, string>)[id] ?? id);
  if (noms.length === 1) return noms[0];
  return `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1].toLowerCase()}`;
}

export function seuilPireBaisse(profil: Profil): number | undefined {
  return profil.pacte.regles.find((r) => r.type === 'pire_baisse_max')?.seuil;
}

/** La règle calculable la plus proche de sa limite : c'est elle que la carte « Votre Pacte » met en avant. */
export function regleCle(profil: Profil): ReglePacte | undefined {
  return profil.pacte.regles
    .filter((r) => r.utilisation !== null)
    .sort((a, b) => (b.utilisation ?? 0) - (a.utilisation ?? 0))[0];
}

/** Texte de la valeur actuelle d'une règle calculable : « −7,8 % au pire », « 15 % du portefeuille ». */
export function valeurRegle(regle: ReglePacte): string | null {
  if (regle.valeur === null) return null;
  if (regle.type === 'pire_baisse_max') return `${pourcent(regle.valeur)} au pire`;
  return `${part(regle.valeur)} du portefeuille`;
}

export interface BilanPacte {
  violations: number;
  verifiees: number;
  aJuger: number;
  statut: Statut;
}

export function bilanPacte(profil: Profil): BilanPacte {
  const calculables = profil.pacte.regles.filter(estCalculable);
  const violations = calculables.filter((r) => r.statut === 'violation').length;
  return {
    violations,
    verifiees: calculables.length - violations,
    aJuger: profil.pacte.regles.length - calculables.length,
    statut: violations ? 'Violation' : 'Conforme',
  };
}

export interface Signalement {
  statut: Statut | null;
  texte: string;
  provenance?: 'Fait';
}

/**
 * Ce que le Pacte dit d'un titre avant toute simulation (recherche, annexe D.3) :
 * exclusions et plafonds par catégorie, critères documentaires selon les sources du dossier.
 */
export function signalementsTitre(profil: Profil, titre: Titre): Signalement[] {
  const signalements: Signalement[] = [];
  profil.pacte.regles.forEach((regle, i) => {
    const numero = i + 1;
    if (regle.type === 'plafond' && regle.categories?.some((c) => titre.categories.includes(c))) {
      signalements.push(regle.max === 0
        ? { statut: 'Violation', texte: `Exclu par votre Pacte (§${numero})` }
        : { statut: 'À vérifier', texte: `Plafonné à ${part(regle.max ?? 0)} par votre Pacte (§${numero})` });
    }
    if (regle.type === 'critere_documentaire' && regle.critere) {
      const libelles = (LIBELLES.criteresDocumentaires as Record<string, Record<string, string>>)[regle.critere] ?? {};
      const document = titre.documents.find((d) => d.critere === regle.critere);
      const autre = titre.documents.find((d) => d.critere !== regle.critere);
      if (document?.valeur === true) signalements.push({ statut: 'Violation', texte: libelles.vrai ?? document.valeurAffichee });
      else if (document?.valeur === false) signalements.push({ statut: 'Conforme', texte: libelles.faux ?? document.valeurAffichee });
      else if (autre) {
        const libelleAutre = (LIBELLES.criteresDocumentaires as Record<string, Record<string, string>>)[autre.critere]?.present;
        signalements.push({ statut: null, provenance: 'Fait', texte: libelleAutre ?? autre.titre });
      } else signalements.push({ statut: 'À vérifier', texte: libelles.sansSource ?? 'Source manquante' });
    }
  });
  return signalements;
}
