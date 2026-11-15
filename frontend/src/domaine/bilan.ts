/**
 * Bilan du Greffier en langage clair. Les contrôles du contrat parlent la langue du Greffier
 * (« Pire baisse −13,5 % au-delà du seuil −12,0 % », « Biais du survivant… ») ; ici, chacun
 * devient une phrase qu'un utilisateur comprend à la première lecture. Rien n'est recalculé :
 * les chiffres viennent du contrat (comparaison, règles du Pacte, valeurs des pièces).
 */
import type { ContratTribunal, RegleContrat } from '../api/contrat';
import type { Controle } from '../api/types';
import { dollars, pourcent, seuil } from '../lib/format';

export type Groupe = 'enfreint' | 'a_juger' | 'verifie';

export interface ControleExplique {
  groupe: Groupe;
  titre: string;
  detail: string;
  regle: string;
  paragraphe?: number;
  pieces: string[];
}

export const GROUPES: { id: Groupe; titre: string; aide: string }[] = [
  { id: 'enfreint', titre: 'Enfreint votre Pacte', aide: 'Une règle que vous avez signée n’est pas respectée par cette décision.' },
  { id: 'a_juger', titre: 'À juger par vous', aide: 'Le calcul ne peut pas trancher : c’est à vous d’en tenir compte.' },
  { id: 'verifie', titre: 'Vérifié', aide: 'Le Greffier a contrôlé ces points : ils sont en règle.' },
];

const GROUPE_DU_STATUT: Record<Controle['statut'], Groupe> = { Violation: 'enfreint', 'À vérifier': 'a_juger', Conforme: 'verifie' };

/** Contrôles du système (pas des règles du Pacte), dits en clair. */
const SYSTEME: Record<string, { titre: string; detail?: string }> = {
  cadre_simulation: { titre: 'Aucun conseil, aucune promesse', detail: 'Aucun argument ne vous dit quoi faire ni ne présente l’avenir comme certain.' },
  performance_passee: { titre: 'Le passé ne prédit pas l’avenir', detail: 'Des arguments s’appuient sur des résultats passés : ils ne garantissent rien pour la suite.' },
  biais_survivant: { titre: 'Un passé un peu trop beau', detail: 'Les titres étudiés ont été choisis en 2026 : ceux qui ont disparu ou chuté manquent, ce qui embellit le passé.' },
  interpretation_demande: { titre: 'Votre demande a été interprétée' },
  coherence_questionnaire: { titre: 'Deux de vos réponses se contredisent' },
  questionnaire: { titre: 'Un type de placement nouveau pour vous' },
};

/** Perte au pire moment en dollars, si la pièce de simulation la donne (pipeline/simulation.py). */
function perteEnDollars(contrat: ContratTribunal): { perte: number; capital: number } | null {
  const piece = contrat.pieces.find((p) => p.outil === 'simuler_portefeuille'
    && typeof p.valeurs.perte_au_pire_moment_cad === 'number' && typeof p.valeurs.capital === 'number');
  return piece ? { perte: piece.valeurs.perte_au_pire_moment_cad as number, capital: piece.valeurs.capital as number } : null;
}

function titreDecision(contrat: ContratTribunal): string {
  return contrat.decision.type === 'position' && contrat.decision.ticker ? contrat.decision.ticker : 'ce panier';
}

function expliquerRegle(c: Controle, regle: RegleContrat, contrat: ContratTribunal): Pick<ControleExplique, 'titre' | 'detail'> {
  const libelle = `« ${regle.libelle} »`;
  const enfreint = c.statut === 'Violation';
  switch (regle.type) {
    case 'pire_baisse_max': {
      const baisse = pourcent(Math.abs(contrat.comparaison.apres.pire_baisse));
      const limite = seuil(Math.abs(regle.seuil ?? 0));
      const dollarsPerdus = perteEnDollars(contrat);
      const enDollars = dollarsPerdus ? `, soit ${dollars(dollarsPerdus.perte)} sur ${dollars(dollarsPerdus.capital)}` : '';
      return enfreint
        ? { titre: 'Au pire moment, la baisse dépasse votre limite',
            detail: `Votre portefeuille perdrait ${baisse} de sa valeur${enDollars}, alors que vous acceptez au plus ${limite}.` }
        : { titre: 'La pire baisse reste dans votre limite',
            detail: `Au pire moment, ${baisse} de baisse${enDollars}, pour une limite de ${limite}.` };
    }
    case 'plafond':
      return { titre: enfreint ? `${libelle} n’est pas respectée` : `${libelle} est respectée`, detail: c.texte.replace(/\s*\(Pacte §\d+\)/, '').replace(/\.?$/, '.') };
    case 'critere_documentaire': {
      const titre = titreDecision(contrat);
      if (enfreint) return { titre: 'Une source documente un conflit avec vos valeurs', detail: `Le dossier contient une source sur ${titre} qui touche votre règle ${libelle}.` };
      if (c.statut === 'À vérifier') return { titre: 'Aucune source pour vérifier vos valeurs', detail: `Le dossier ne contient aucune source sur ${titre} pour votre règle ${libelle} : le Greffier ne peut pas conclure.` };
      return { titre: 'Aucun conflit documenté avec vos valeurs', detail: `Votre règle ${libelle} est respectée selon les sources du dossier.` };
    }
    default:
      return { titre: libelle, detail: 'Cette règle ne se calcule pas : c’est à vous d’en juger.' };
  }
}

export function expliquerControle(c: Controle, contrat: ContratTribunal): ControleExplique {
  const base = { groupe: GROUPE_DU_STATUT[c.statut], regle: c.regle, paragraphe: c.paragraphe, pieces: c.pieces };
  const regle = contrat.pacte.regles.find((r) => r.id === c.regle);
  if (regle) return { ...base, ...expliquerRegle(c, regle, contrat) };
  if (c.regle === 'verifier_chiffres') {
    const compte = c.texte.match(/(\d+\/\d+) chiffres/)?.[1];
    return c.statut === 'Conforme'
      ? { ...base, titre: 'Aucun chiffre inventé', detail: `Chaque chiffre cité par le Procureur et l’Avocat a été retrouvé dans les calculs${compte ? ` (${compte})` : ''}.` }
      : { ...base, titre: 'Des chiffres n’ont pas été retrouvés', detail: c.texte };
  }
  const connu = SYSTEME[c.regle];
  return { ...base, titre: connu?.titre ?? c.texte, detail: connu?.detail ?? (connu ? c.texte : '') };
}

export interface Bilan {
  ton: 'violation' | 'a_juger' | 'conforme';
  /** Le compte des règles enfreintes ; l'explication de chacune reste sous sa règle. */
  verdict: string;
  controles: ControleExplique[];
  comptes: Record<Groupe, number>;
}

export function bilanGreffier(controles: Controle[], contrat: ContratTribunal): Bilan {
  const expliques = controles.map((c) => expliquerControle(c, contrat));
  const comptes = { enfreint: 0, a_juger: 0, verifie: 0 };
  expliques.forEach((c) => { comptes[c.groupe] += 1; });
  const duPacte = expliques.filter((c) => c.paragraphe !== undefined);
  const enfreintes = duPacte.filter((c) => c.groupe === 'enfreint');
  const aJuger = duPacte.filter((c) => c.groupe === 'a_juger');
  if (enfreintes.length) {
    return {
      ton: 'violation',
      verdict: enfreintes.length > 1 ? `${enfreintes.length} règles de votre Pacte sont enfreintes` : '1 règle de votre Pacte est enfreinte',
      controles: expliques,
      comptes,
    };
  }
  if (aJuger.length) {
    return { ton: 'a_juger', verdict: `Rien d’enfreint, mais ${aJuger.length > 1 ? `${aJuger.length} règles sont` : '1 règle est'} à juger par vous`, controles: expliques, comptes };
  }
  return { ton: 'conforme', verdict: 'Votre décision respecte votre Pacte', controles: expliques, comptes };
}
