/**
 * « Essayez de tromper le Greffier » (#69) : un argument tapé à la main est vérifié par le
 * Greffier (POST /verifier, outil 6, Python seul) contre les pièces citées du procès affiché.
 * Chaque nombre s'affiche trouvé (avec sa pièce) ou introuvable (avec le motif exact).
 */
import { useId, useState, type FormEvent } from 'react';
import type { Piece, ResultatTribunal, ResultatVerification } from '../api/types';
import { greffierEnDirect, verifierArgument } from '../api/tribunal';
import { pieges } from '../domaine/pieges';
import { nombre } from '../lib/format';
import { Bouton } from './Bouton';
import { Icone } from './Icone';
import styles from './TrompezLeGreffier.module.css';

const LONGUEUR_MAX = 600;

function libelleSource(source: string): string {
  if (source === 'décision') return 'dans la décision';
  if (source === 'période') return 'dans la période analysée';
  return `dans ${source}`;
}

export function TrompezLeGreffier({ resultat, pieces }: { resultat: ResultatTribunal; pieces: Piece[] }) {
  const [texte, setTexte] = useState('');
  const [citees, setCitees] = useState<string[]>([]);
  const [verification, setVerification] = useState<ResultatVerification | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const idTexte = useId();
  const idCompteur = useId();
  const disponible = greffierEnDirect(resultat.procesId);
  const exemples = pieges(resultat);
  const piecesDuProces = pieces.filter((p) => p.origine !== 'question');

  const verifier = async (e?: FormEvent, contenu = texte, references = citees) => {
    e?.preventDefault();
    if (!resultat.procesId || !contenu.trim()) return;
    setEnvoi(true);
    setErreur(null);
    try {
      setVerification(await verifierArgument(resultat.procesId, contenu, references));
    } catch (err) {
      setVerification(null);
      setErreur(err instanceof Error ? err.message : String(err));
    } finally {
      setEnvoi(false);
    }
  };

  const basculer = (code: string) => setCitees((c) => (c.includes(code) ? c.filter((x) => x !== code) : [...c, code]));

  return (
    <section className={styles.section} aria-labelledby="titre-pieges">
      <div className={styles.entete}>
        <h2 className="t-intertitre" id="titre-pieges">Essayez de tromper le Greffier</h2>
        <p className="t-petit c-700">
          Écrivez un argument chiffré et citez des pièces : le Greffier vérifie chaque nombre avec les mêmes règles que pour
          le Procureur et l'Avocat. Python seul, sans IA : la réponse est immédiate.
        </p>
      </div>

      {!disponible ? (
        <p className="t-petit c-700" role="note">
          Le Greffier en direct a besoin de l'adresse de la Lambda (VITE_API_URL) et d'un procès archivé dans S3.
        </p>
      ) : (
        <form className={styles.formulaire} onSubmit={verifier}>
          {exemples.length > 0 && (
            <div className={styles.exemples} role="group" aria-label="Exemples prêts">
              {exemples.map((ex) => (
                <button
                  key={ex.id}
                  type="button"
                  className={styles.exemple}
                  onClick={() => {
                    setTexte(ex.texte);
                    setCitees(ex.pieces);
                    void verifier(undefined, ex.texte, ex.pieces);
                  }}
                >
                  {ex.libelle}
                </button>
              ))}
            </div>
          )}
          <label htmlFor={idTexte} className="t-petit-fort">Votre argument</label>
          <textarea
            id={idTexte}
            className={styles.texte}
            rows={2}
            maxLength={LONGUEUR_MAX}
            value={texte}
            aria-describedby={idCompteur}
            placeholder="Ex. : Avec cette décision, la pire baisse atteint −40 %."
            onChange={(e) => setTexte(e.target.value)}
          />
          <span id={idCompteur} className={`t-petit c-500 ${styles.compteur}`}>{texte.length} / {LONGUEUR_MAX} caractères</span>
          <fieldset className={styles.pieces}>
            <legend className="t-petit-fort">Pièces citées</legend>
            {piecesDuProces.map((p) => (
              <label key={p.code} className={styles.piece} title={p.titre}>
                <input type="checkbox" checked={citees.includes(p.code)} onChange={() => basculer(p.code)} />
                <span className="t-trace">{p.code}</span>
                <span className="visuellement-cache"> : {p.titre}</span>
              </label>
            ))}
          </fieldset>
          <Bouton type="submit" variante="secondaire" fleche={false} disabled={envoi || !texte.trim()} className={styles.verifier}>
            {envoi ? 'Vérification…' : 'Faire vérifier par le Greffier'}
          </Bouton>
        </form>
      )}

      <div aria-live="polite">
        {erreur && <p className={`t-petit ${styles.erreur}`}>{erreur}</p>}
        {verification && (
          <div className={`${styles.resultat} ${verification.valide ? styles.accepte : styles.rejete}`}>
            <p className={styles.verdict}>
              <Icone nom={verification.valide ? 'check' : 'interdit'} taille={18} />
              <span className="t-intertitre">
                {verification.valide ? 'Argument accepté' : 'Argument rejeté'}
              </span>
              <span className="t-petit c-700">
                {verification.nombres.length
                  ? `${verification.compte} chiffres prouvés`
                  : 'aucun chiffre à vérifier'} · vérifié en {nombre(verification.dureeMs)}{' '}ms
              </span>
            </p>
            {verification.motif && !verification.nombres.some((n) => n.motif) && (
              <p className="t-petit">{verification.motif}</p>
            )}
            <ul className={styles.nombres}>
              {verification.nombres.map((n, i) => (
                <li key={`${n.texte}-${i}`} className={styles.nombre}>
                  <span className={`${styles.etat} ${n.trouve ? styles.trouve : styles.introuvable}`}>
                    <Icone nom={n.trouve ? 'check' : 'interdit'} taille={14} />
                    {n.trouve ? 'Trouvé' : 'Introuvable'}
                  </span>
                  <span className="t-tableau-fort">{n.texte}</span>
                  <span className="t-petit c-700">
                    {n.trouve ? n.sources.map(libelleSource).join(', ') : n.motif ?? 'absent des pièces citées'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
