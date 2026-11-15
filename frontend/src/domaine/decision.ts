/**
 * Décision en cours d'instruction : libellé, demande envoyée au Tribunal, lecture des
 * tables précalculées, effets sur le Pacte et messages. Tout vient des tables et du Pacte.
 */
import type { DecisionContrat } from '../api/contrat';
import type { DecisionUI, EntreeSimulation, Profil, Statut, TablePanier, TablePosition } from '../api/types';
import { nomTitre, titre as titreDe } from '../api/donnees';
import { date, part, pourcent } from '../lib/format';
import { estCalculable, libelleCategories, paragraphe, statutUi } from './pacte';

export function totalPanier(decision: DecisionUI): number {
  return decision.type === 'panier' ? decision.lignes.reduce((s, l) => s + l.poids, 0) : decision.taille;
}

/** « 30 % en TSLA » (même forme que le libellé du pipeline) ou « Panier de 4 titres ». */
export function libelleDecision(decision: DecisionUI): string {
  if (decision.type === 'position') return `${decision.taille} % en ${decision.ticker}`;
  return `Panier de ${decision.lignes.length} titre${decision.lignes.length > 1 ? 's' : ''}`;
}

/** Phrase envoyée à l'Agent Profil du Tribunal (`POST /tribunal`). */
export function demandeDecision(decision: DecisionUI): string {
  if (decision.type === 'position') {
    return `Je veux mettre ${decision.taille} % de mon portefeuille en ${nomTitre(decision.ticker)} (${decision.ticker})`;
  }
  const lignes = decision.lignes.map((l) => `${l.poids} % ${nomTitre(l.ticker)} (${l.ticker})`).join(', ');
  return `Je veux réallouer tout mon portefeuille vers un panier : ${lignes}`;
}

/** Vrai si le contrat d'un procès juge exactement cette décision. */
export function correspondAuContrat(decision: DecisionUI, contrat: DecisionContrat): boolean {
  if (decision.type === 'position' && contrat.type === 'position') {
    return contrat.ticker === decision.ticker && Math.round(contrat.taille * 100) === decision.taille
      && contrat.financement === 'proportionnel';
  }
  if (decision.type === 'panier' && contrat.type === 'reallocation') {
    if (Math.round(contrat.part_reallouee * 100) !== 100 || contrat.panier.length !== decision.lignes.length) return false;
    return decision.lignes.every((l) => contrat.panier.some((p) => p.ticker === l.ticker && Math.round(p.poids * 100) === l.poids));
  }
  return false;
}

/** Clé d'une composition dans la table du panier (« 25-25-25-25 »), ou null si elle n'est pas précalculée. */
export function cleComposition(lignes: { ticker: string; poids: number }[], table: TablePanier): string | null {
  if (lignes.some((l) => !table.candidats.includes(l.ticker))) return null;
  if (lignes.some((l) => l.poids % table.pas !== 0)) return null;
  if (lignes.reduce((s, l) => s + l.poids, 0) !== 100) return null;
  return table.candidats.map((t) => lignes.find((l) => l.ticker === t)?.poids ?? 0).join('-');
}

export function entreePosition(table: TablePosition, taille: number): EntreeSimulation & { taille: number } {
  return table.tailles[Math.max(0, Math.min(table.tailles.length - 1, Math.round(taille)))];
}

export function entreePanier(table: TablePanier, lignes: { ticker: string; poids: number }[]): EntreeSimulation | null {
  const cle = cleComposition(lignes, table);
  return cle ? table.compositions[cle] ?? null : null;
}

export interface Effet {
  libelle: string;
  avant: string;
  apres: string;
  limite: string;
  statut?: Statut;
  regle?: string;
}

/** Cartes « avant → après » de l'écran Décision : plafonds concernés, chute maximale, rendement. */
export function effetsSurLePacte(profil: Profil, entree: EntreeSimulation, decision: DecisionUI): Effet[] {
  const effets: Effet[] = [];
  const regles = profil.pacte.regles;
  for (const regle of regles.filter((r) => r.type === 'plafond')) {
    const avant = regle.valeur ?? 0;
    const apres = entree.parts[regle.id] ?? 0;
    if (decision.type === 'position' && avant === 0 && apres === 0) continue;
    effets.push({
      libelle: libelleCategories(regle.categories ?? []),
      avant: part(avant),
      apres: part(apres),
      limite: regle.max === 0 ? 'exclu par votre Pacte' : `maximum ${part(regle.max ?? 0)}`,
      statut: statutUi(entree.statuts[regle.id]),
      regle: regle.id,
    });
  }
  const pireBaisse = regles.find((r) => r.type === 'pire_baisse_max');
  effets.push({
    libelle: 'Chute maximale',
    avant: pourcent(profil.actuel.chuteMax),
    apres: pourcent(entree.chuteMax),
    limite: pireBaisse ? `limite ${pourcent(pireBaisse.seuil ?? 0, { decimales: 0 })}` : 'aucune limite dans votre Pacte',
    statut: pireBaisse ? statutUi(entree.statuts[pireBaisse.id]) : undefined,
    regle: pireBaisse?.id,
  });
  effets.push({
    libelle: 'Rendement annualisé',
    avant: pourcent(profil.actuel.rendement, { signe: true }),
    apres: pourcent(entree.rendement, { signe: true }),
    limite: `par an sur ${Math.round((Date.parse(profil.fin) - Date.parse(profil.debut)) / 3.15576e10)} ans`,
  });
  return effets;
}

export interface MessageDecision {
  type: 'Violation' | 'À vérifier';
  titre: string;
  corps: string;
  aide?: string;
  correction?: { libelle: string; taille: number };
  source?: string;
}

const SUITE = 'Vous pouvez soumettre quand même : le Tribunal en débattra.';

/** Messages de l'écran Décision : règles calculables enfreintes, puis critères documentaires. */
export function messagesDecision(
  profil: Profil,
  entree: EntreeSimulation | null,
  decision: DecisionUI,
  maxConforme: number | null,
): MessageDecision[] {
  const messages: MessageDecision[] = [];
  const regles = profil.pacte.regles;
  const position = decision.type === 'position';

  if (entree) {
    const enfreintes = regles.filter((r) => estCalculable(r) && entree.statuts[r.id] === 'violation');
    if (enfreintes.length) {
      const sujet = position ? 'Cette taille' : 'Ce panier';
      const titre = enfreintes.length === 1
        ? `${sujet} enfreint votre Pacte (§${paragraphe(regles, enfreintes[0].id)})`
        : `${sujet} enfreint ${enfreintes.length} règles de votre Pacte`;
      const morceaux = enfreintes.map((r) => {
        if (r.type === 'pire_baisse_max') {
          const seuil = pourcent(r.seuil ?? 0, { decimales: 0 });
          if (position && maxConforme !== null && enfreintes.length === 1) {
            return `Au-delà de ${maxConforme} %, la pire chute observée dépasse votre limite de ${seuil}.`;
          }
          return `pire chute de ${pourcent(entree.chuteMax)} pour une limite de ${seuil}`;
        }
        const nom = libelleCategories(r.categories ?? []).toLowerCase();
        const valeur = part(entree.parts[r.id] ?? 0);
        return r.max === 0 ? `${nom} à ${valeur}, alors que votre Pacte les exclut`
          : `${nom} à ${valeur} pour ${part(r.max ?? 0)} permis`;
      });
      const corps = morceaux.length === 1 && morceaux[0].endsWith('.')
        ? morceaux[0]
        : `${morceaux.join(', ').replace(/^./, (c) => c.toUpperCase())}.`;
      const correction = position && maxConforme !== null && maxConforme < decision.taille
        ? { libelle: `Ramener à ${maxConforme} %`, taille: maxConforme } : undefined;
      messages.push({
        type: 'Violation',
        titre,
        corps: `${corps} ${position ? SUITE : `${SUITE.slice(0, -1)} et cherchera la plus grande part réallouable compatible.`}`,
        correction,
      });
    }
  }

  const tickers = decision.type === 'position' ? [decision.ticker] : decision.lignes.map((l) => l.ticker);
  for (const regle of regles.filter((r) => r.type === 'critere_documentaire' && r.critere)) {
    const numero = paragraphe(regles, regle.id);
    const documentes = tickers.map((t) => ({ t, doc: titreDe(t)?.documents.find((d) => d.critere === regle.critere) }));
    const enConflit = documentes.filter((d) => d.doc?.valeur === true);
    const sansSource = documentes.filter((d) => !d.doc);
    if (enConflit.length) {
      const { t, doc } = enConflit[0];
      messages.push({
        type: 'Violation',
        titre: `Vos valeurs : en conflit avec votre Pacte (§${numero})`,
        corps: `Une source du dossier documente une controverse pour ${nomTitre(t)} : ${doc!.valeurAffichee.replace(/^[^:]+:\s*/, '')}. Votre Pacte pose la règle « ${regle.libelle} ». ${SUITE}`,
        source: `${doc!.titre} · consultée le ${date(doc!.dateConsultation)}`,
      });
    } else if (sansSource.length) {
      const noms = sansSource.map((d) => nomTitre(d.t)).join(', ');
      messages.push({
        type: 'À vérifier',
        titre: `Vos valeurs : à vérifier (Pacte §${numero})`,
        corps: `Le dossier ne contient aucune source sur ${noms} pour la règle « ${regle.libelle} ». Sans source documentée, le Greffier ne pourra pas conclure.`,
        aide: 'Vous pouvez continuer : le Tribunal signalera la lacune.',
      });
    }
  }
  return messages;
}

/** Fiche d'un titre : « TSLA · action · NASDAQ · USD — volatilité ≈ 59 %, pire chute −70,9 % sur 5 ans, en CAD ». */
export function ficheTitre(ticker: string, debut: string, fin: string): string {
  const t = titreDe(ticker);
  if (!t) return ticker;
  const annees = Math.round((Date.parse(fin) - Date.parse(debut)) / 3.15576e10);
  return `${t.ticker} · ${t.classe} · ${t.bourse} · ${t.devise} — volatilité ≈ ${pourcent(t.volatilite, { decimales: 0 })}, pire chute ${pourcent(t.chuteMax)} sur ${annees} ans, en CAD`;
}
