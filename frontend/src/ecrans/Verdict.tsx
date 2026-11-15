/**
 * Écran Verdict (annexe C.6). L'utilisateur tranche ; « Signer le verdict » n'exécute rien,
 * il archive le choix (POST /verdict en mode direct, journal local en démonstration).
 */
import { useId, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import type { Profil } from '../api/types';
import { archiverVerdict, ouvrirProcesVerbal } from '../api/tribunal';
import { Gabarit, useTitre } from '../components/Gabarit';
import { Bouton } from '../components/Bouton';
import { Statut } from '../components/Etiquettes';
import { LienRetour, Message } from '../components/Elements';
import { pourcent, seuil as seuilTexte } from '../lib/format';
import { archivage, optionsVerdict, statutDecision, type OptionVerdict } from '../domaine/verdict';
import { useEtatProfil } from '../state/store';
import { useTables } from '../state/useTables';
import { LimitesDonnees } from '../components/Limites';
import styles from './Verdict.module.css';

const LONGUEUR_MAX = 280;

function aujourdhui(): string {
  return new Date().toLocaleDateString('en-CA');
}

/** Échelle commune des jauges : la plus forte baisse ou le plus bas seuil de l'écran, avec une marge. */
function echelleJauges(options: OptionVerdict[]): number {
  const valeurs = options.flatMap((o) => [o.pireBaisse, o.seuil, o.ancienSeuil]).filter((v): v is number => v !== undefined);
  return Math.max(0.05, ...valeurs.map(Math.abs)) * 1.1;
}

/**
 * La pire baisse de l'option face au seuil du Pacte : on voit si elle le dépasse sans lire les chiffres.
 * Décorative (aria-hidden) : les mêmes nombres sont écrits dans la carte.
 */
function JaugeBaisse({ valeur, seuil, ancienSeuil, echelle }: { valeur: number; seuil: number; ancienSeuil?: number; echelle: number }) {
  const position = (v: number) => `${Math.min(100, (Math.abs(v) / echelle) * 100)}%`;
  const depasse = valeur < seuil - 1e-9;
  return (
    <span className={styles.jauge} aria-hidden="true">
      <span className={styles.piste}>
        <span className={`${styles.barre} ${depasse ? styles.depasse : ''}`} style={{ width: position(valeur) }} />
        <span className={styles.repere} style={{ left: position(seuil) }} />
      </span>
      <span className={styles.legendeJauge}>
        <span className={styles.marqueSeuil} />
        <span className="t-petit c-500">
          {ancienSeuil !== undefined ? `Seuil ajusté ${pourcent(seuil)} (au lieu de ${seuilTexte(ancienSeuil)})` : `Seuil du Pacte ${seuilTexte(seuil)}`}
        </span>
      </span>
    </span>
  );
}

export function Verdict({ profil }: { profil: Profil }) {
  useTitre('Verdict');
  const navigate = useNavigate();
  const { etat, modifierVerdict, signer } = useEtatProfil(profil.id);
  const { decision, tribunal, verdict } = etat;
  const { tablePosition, entree } = useTables(profil, decision);
  const [erreur, setErreur] = useState<string | null>(null);
  const [erreurExport, setErreurExport] = useState<string | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const idRaison = useId();
  const idJustification = useId();
  const idCompteur = useId();
  const idArchive = useId();

  if (!decision || tribunal.statut !== 'pret' || !tribunal.resultat) return <Navigate to={`/${profil.id}/tribunal`} replace />;
  const resultat = tribunal.resultat;
  const options = optionsVerdict({ profil, resultat, decision, table: tablePosition, entreeDecision: entree });
  const choisie: OptionVerdict | undefined = options.find((o) => o.id === verdict.option);
  const statut = statutDecision(profil, resultat);
  const violations = resultat.controles.filter((c) => c.paragraphe !== undefined && c.statut === 'Violation').length;
  const echelle = echelleJauges(options);
  const dateLongue = new Date().toLocaleDateString('fr-CA', { day: 'numeric', month: 'long', year: 'numeric' });

  const raisonBlocage = !choisie
    ? 'Choisissez une option pour signer le verdict.'
    : choisie.engagement && (!verdict.justification.trim() || !verdict.compris)
      ? 'Pour maintenir malgré la violation, écrivez pourquoi et cochez la case : la signature reste désactivée jusque-là.'
      : null;

  const exporterProcesVerbal = async () => {
    setErreurExport(null);
    try {
      await ouvrirProcesVerbal(resultat.procesId);
    } catch (e) {
      setErreurExport(e instanceof Error ? e.message : String(e));
    }
  };

  const signerVerdict = async () => {
    if (raisonBlocage || !choisie) return;
    setEnvoi(true);
    setErreur(null);
    try {
      await archiverVerdict(resultat.procesId, choisie.verdict);
      const { resume, journal, statut: statutJournal } = archivage(choisie, decision, violations);
      signer(resume, { date: aujourdhui(), texte: journal, statut: statutJournal });
      navigate(`/${profil.id}/portefeuille?archive=1`);
    } catch (e) {
      setErreur(e instanceof Error ? e.message : String(e));
      setEnvoi(false);
    }
  };

  const carte = (option: OptionVerdict) => {
    const selectionnee = verdict.option === option.id;
    return (
      <li key={option.id} className={`${styles.option} ${selectionnee ? styles.selectionnee : ''}`}>
        <label className={styles.etiquetteOption}>
          <input
            type="radio"
            name="verdict"
            value={option.id}
            checked={selectionnee}
            onChange={() => modifierVerdict({ option: option.id })}
            className={styles.radio}
          />
          <span className={styles.texteOption}>
            <span className={styles.ligneTitre}>
              <span className="t-corps-fort">{option.titre}</span>
              {option.statut && <Statut type={option.statut} />}
            </span>
            {option.sousTitre && <span className="t-petit c-700">{option.sousTitre}</span>}
            {option.ajustements && option.ajustements.length > 0 && (
              <span className={styles.ajustements}>
                {option.ajustements.map((a) => (
                  <span key={a.regle} className={`t-petit-fort ${styles.ajustement}`} data-ajustement={a.regle}>
                    {a.texte}
                    {a.pieces.map((code) => (
                      <span key={code} className="t-petit">
                        {' '}
                        <Link to={`/${profil.id}/tribunal?piece=${code}`} className={styles.lienPiece} aria-label={`Ouvrir la pièce ${code}`}>{code}</Link>
                      </span>
                    ))}
                  </span>
                ))}
              </span>
            )}
            {option.mesures.length > 0 && (
              <span className={styles.mesures}>
                {option.mesures.map((m) => (
                  <span key={m.libelle}>
                    <span className="t-petit c-500">{m.libelle}</span>{' '}
                    <span className="t-tableau-fort">{m.valeur}</span>
                  </span>
                ))}
              </span>
            )}
            {option.pireBaisse !== undefined && option.seuil !== undefined && (
              <JaugeBaisse valeur={option.pireBaisse} seuil={option.seuil} ancienSeuil={option.ancienSeuil} echelle={echelle} />
            )}
          </span>
        </label>
        {selectionnee && option.engagement && (
          <div className={styles.engagement}>
            <label htmlFor={idJustification} className={styles.libelleJustification}>
              <span className="t-corps-fort">Pourquoi maintenir malgré la violation ?</span>
              <span className="t-petit c-500"> obligatoire</span>
            </label>
            <div className={styles.zoneTexte}>
              <textarea
                id={idJustification}
                maxLength={LONGUEUR_MAX}
                rows={2}
                required
                aria-required="true"
                aria-describedby={idCompteur}
                value={verdict.justification}
                onChange={(e) => modifierVerdict({ justification: e.target.value })}
              />
              <span id={idCompteur} className="t-petit c-500">{verdict.justification.length} / {LONGUEUR_MAX} caractères</span>
            </div>
            <label className={styles.case}>
              <input type="checkbox" checked={verdict.compris} required onChange={(e) => modifierVerdict({ compris: e.target.checked })} />
              <span className="t-petit">{option.engagement}</span>
            </label>
          </div>
        )}
        {selectionnee && option.noteSiChoisie && <p className={`t-petit ${styles.note}`}>{option.noteSiChoisie}</p>}
      </li>
    );
  };

  return (
    <Gabarit nomProfil={profil.nom} idProfil={profil.id} etape="verdict">
      <div className={styles.corps}>
        <LienRetour vers={`/${profil.id}/tribunal`}>Tribunal</LienRetour>
        <div className={styles.titre}>
          <h1 className="t-h1">Quelle est votre décision ?</h1>
          <p className={styles.rappel}>
            <Statut type={statut} />
            <span className="t-corps c-700">{resultat.constat}</span>
          </p>
        </div>

        {/* Paysage (#103) : les choix à gauche ; ce que la signature archive et les limites à droite, fixes au défilement. */}
        <div className={styles.grille}>
          <div className={styles.cote}>
            <section className={styles.blocArchive} aria-labelledby={idArchive}>
              <h2 id={idArchive} className="t-etiquette c-500">Ce que la signature archive</h2>
              <ul className={styles.listeArchive}>
                <li className="t-petit">
                  <span className="t-petit-fort">{choisie ? choisie.titre : 'Votre choix'}</span>, daté du {dateLongue}
                </li>
                <li className="t-petit">
                  Les {resultat.contrat.pieces.length} pièces et les {resultat.contrat.controles.length} contrôles du procès
                </li>
                {choisie?.engagement && <li className="t-petit">Votre justification du maintien malgré {violations > 1 ? 'les violations' : 'la violation'}</li>}
              </ul>
              <p className="t-petit c-700">Rien n'est exécuté : aucune transaction, seulement une archive.</p>
              <Bouton variante="secondaire" compact fleche={false} className={styles.lienExport} onClick={exporterProcesVerbal}>
                Exporter le procès-verbal
              </Bouton>
              {erreurExport && (
                <Message type="Violation" titre="Le procès-verbal n'a pas pu être produit" correction={{ libelle: 'Réessayer', onClick: exporterProcesVerbal }}>
                  <p>{erreurExport}</p>
                </Message>
              )}
            </section>
            <LimitesDonnees ecran="verdict" titre="Avant de signer : ce que le procès ne dit pas" variante="panneau" ouvertParDefaut={false} />
          </div>

          <div className={styles.choix}>
            <fieldset className={styles.options}>
              <legend className="visuellement-cache">Votre décision sur « {resultat.titre} »</legend>
              <ul>{options.map(carte)}</ul>
            </fieldset>

            {erreur && (
              <Message type="Violation" titre="Le verdict n'a pas pu être archivé" correction={{ libelle: 'Réessayer', onClick: signerVerdict }}>
                <p>{erreur}</p>
              </Message>
            )}
          </div>

          <div className={styles.suite}>
            <div className={styles.actions}>
              {raisonBlocage && <p id={idRaison} className={`t-petit c-700 ${styles.raison}`}>{raisonBlocage}</p>}
              <Bouton
                variante="primaire"
                onClick={signerVerdict}
                aria-disabled={Boolean(raisonBlocage) || envoi || undefined}
                aria-describedby={raisonBlocage ? idRaison : undefined}
              >
                {envoi ? 'Archivage…' : 'Signer le verdict'}
              </Bouton>
            </div>
          </div>
        </div>
      </div>
    </Gabarit>
  );
}
