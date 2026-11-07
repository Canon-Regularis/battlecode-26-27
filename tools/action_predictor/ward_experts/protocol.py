"""Freeze four fits and both decoders before any specialist is fitted."""
import json
from pathlib import Path
from ..consistent_data import ROOT,BASE,JOBS
from ..audit import immutable_json
from ..data import digest

WORK=ROOT/'.cambc/action-predictor/v14';REPORT=ROOT/'tools/action_predictor/experiments/v14'
FITS=('P00','P01','T00','T01')

def freeze():
    WORK.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    value=dict(id='ward-specialists',budget=dict(initial_training_fits=4,arms={'P00':'ward-only neural placement with frozen128context and20tilefeatures;richwardblocks zero','P01':'sameplacementarchitecture with personallyobservableward/visibleentity/history features','T00':'small binaryward specialist on frozencontext andbasePRE/history;richwardblocks zero','T01':'samebinaryarchitecture with additionalward-specificfeatures'}),
        control='Frozen G00 original action-first complete predictor, P05priority and G00movement retained. B00 also retained as contextual baseline; its zero wardtypes make it uninformative as the sole head-only control.',
        treatments={'A':'P01placement only; EXACTLY unchanged G00 predicted action choices','B':'T01ward probability, originalconditionalward coordinates','C':'T01probability plusP01placement. P00/T00areprespecifiedsimplercontrols, notretrospective substitutes ifP01/T01 lose.'},
        probability='Factorized normalized type*conditionalparameter distribution. Binaryp replaces P(ward);nonwardtypes rescaled proportionally to sum1-p. Placement is .9999learned probability on historicalrange2personal candidate tiles plus.0001frozenQwardfullsupport;emptycandidate contexts reuseQward. No opaque fallbackgate, oraclefamilyrouting,thresholdsweep or fabricatedshoparguments.',
        decoders='PRIMARY preserves the requested A head-only intervention: allarms use typeargmax thenconditionalargmax, matching originalG00; explicitly NOT claimed jointMAP. Separate SECONDARY fulljointMAP ranks actual fullcommand probability across allfamilymodes in EVERYarm against Q00; it maychange types in A and is labeled separately. Neither decoder chosen retrospectively.',
        inputs='Only personalPRE/publicgeometry,championtype(notgameentityID),knownliving ally/enemy/campgeometry,wardcharges/recharge/channel/readiness,actual earlier own-actionhistory,personallyAPI-authorizedexistingward positions/status/radius. Geometriccoverage indicators are NOT certified LOSvision. No currentrecordedfamily/position for inference.',
        semantics='Pinned engines2/3 SDKrange getter andbitboard drawChebyshev2,publicinmap geometry,knownallywardcell exclusion. No hypotheticalaction simulation. Fullterrain/enginelegality notcertified beyond availableSDKconstraints; report all unsupported labels, retainfullsupportlikelihood,neverdroprows.',
        extraction='Query everyeligible selected personalPRE with aliveownposition andwardcharges>0, regardless recordedaction orprediction, includingchannelled/recallhardnegatives. Otherrows explicitlyunavailable;charges/position alsoencoded. No newdownloads or matches.',
        sampling='Placement trains ALL10842recordedaugmentedTRAINwardrows. Typing trains ALL433071TRAINrows, Bernoulli losswithTRAIN-onlypositive/negativeclasspriorweights matching naturalwardprevalence; this corrects classmarginals only, notunknownwithinclassselectionprobabilities. No nonwarddrops/hardnegative-onlydenominator. NaturalTRAINandallaugTRAINreported separately.',
        selection=dict(seed=20261112,max_rounds=35,patience=6,improvement=.0001,criterion='full original14439DEV observedjointNLL;placement substitutesonlywardparameterloss,typing substitutesBernoullitypeloss. No retrospective checkpoint/threshold choice.',placement_batch=128,type_batch=512,optimizer='AdamW',lr=.001,weight_decay=.01,dropout=.1),
        metrics=['WardbinaryPRF/calibrationatfixed.5 diagnostic and actual15waypredictedwardPRF separately','alltruefamilyexactwardplacement and correctlytypedconditional exact','jointwardcommands andtype/jointfalsepositives','recall->ward','all14categoryjoint/type/confusion/conditionalparameters','overallstrictmacroF1 andobservedjointNLL','paired2000wholegroupresamples seed20261106','TRAINnatural/aug vsDEV,champion/engine/contextsupport,learningcurves','physicalcandidatecoverage separatefromlearnedaccuracy'],
        continuation='Execute fourprespecifiedfits subjecttoinput/semanticschecks, fresh requested Solxhighreview afterEACHfit. No furtherarchitectureexpansion. A meaningfulpartialbenefit requires jointward>=14/112, wardF1gain>=.05 vsG00, no increase282wardtypeFP,overalljointdrop<=.002,macrodrop<=.005,noattack/castjointdrop>.02 ormovementdrop>.005,pairedwardgainlower>0. Exploratoryrepeatallocation criterion ONLY; original>=90%everyadequatelysupportedcategory andmacro/movement/NLL/targeting/three-seed goals unchanged. Additionalseedbudget declaredseparatelybeforeanyrepeat; no robustnessclaimfromsingle seed.',
        preservation='Originalbenchmark/splits/groups/dedup andeveryDEVrowfixed;bothreserved75+75sealed. Shops43unassessedstrictfailures andmissingargumentlikelihoodabsent. Sparsealtar/teleport/submituncertified;entityidentityambiguityretained. No playingbotchanges/deployment. PR11DRAFT only,unmerged,noautomerge/queue.',
        deferred='Unrun V13B01/B02deferred bynewuserwardpriority;partialmemoryrepaircache preserved,no additionalgoal/memoryfit.',jobs_sha256=digest(JOBS),sources={str((Path(__file__).parent/n).relative_to(ROOT)):digest(Path(__file__).parent/n) for n in ('protocol.py','personal.cjs','features.py','data.py','model.py','integration.py','fit.py')},new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'protocol.json',value);return value

if __name__=='__main__':freeze()
