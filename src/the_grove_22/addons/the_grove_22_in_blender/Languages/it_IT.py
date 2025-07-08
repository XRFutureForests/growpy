# coding=utf-8

dictionary = {

    "": "",

    # Panel titles
    "panel_presets": "Predefinito",
    "panel_twigs": "Rametti",
    "panel_twigs_more": "Altre",
    "panel_simulation": "Simula",
    "panel_auto_prune": "Potatura Annuale",
    "panel_favor": "Favorisci",
    "panel_drop": "Caduta",
    "panel_add": "Aggiungi",
    "panel_grow": "Accresci",
    "panel_turn": "Gira",
    "panel_react": "Reagisci",
    "panel_thicken": "Ispessisci",
    "panel_build_base": "Base",
    "panel_bend": "Piega",
    "panel_shade": "Ombra",
    "panel_build": "Costruisci",
    "panel_build_texture": "Texture",
    "panel_build_wind": "Vento",


    # User preferences
    "set_twigs_path": "Scegli la cartella rametti...",
    "twigs_path": "Cartella rametti",
    "twigs_path_tt":
        "Indica la cartella in cui salvi i rametti. "
        "Questi rametti saranno elencati nel selettore rametti.",

    "set_textures_path":"Scegli la cartella texture...",
    "textures_path": "Cartella cortecce",
    "textures_path_tt":
        "Indica la cartella in cui salvi le texture della corteccia. "
        "Queste texture saranno elencate nel selettore texture.",

    "save_preferences": "Salva_preferenze",
    "save_preferences_tt": "Salvate le vostre preferenze per ricordare questa impostazione.",


    # Interface messages
    "remove_preset_info": "Rimuovi {}?",
    "overwrite_preset_info": "Sovrascrivi {}?",
    "name_preset_info": "Nome preset.",
    "height_info":  "{:.1f} m",
    "age_info": "{} cicli",
    "branch_info": "{} ramo",
    "branches_info": "{} rami",
    "polygons_info": "{:,} facce",
    "wind_loop_info": "Con {} forme, cicli di vento ogni {} fotogrammi.",
    "tips_info": "Per favore, leggi i suggerimenti nel tooltip:",


    # Presets
    "presets_menu": "",  # Read
    "presets_menu_tt": "Carica le pre-impostazioni dei parametri delle specie di alberi",

    "preset_name": "Nuovo Nome",
    "preset_name_tt": "Nome della preimpostazione da salvare o sovrascrivere",

    "remove_preset": "Rimuovi",
    "remove_preset_tt": "Rimuovi le pre-impostazioni selezionate",

    "cancel_action": "Annulla",

    "remove_preset_confirm": "Sì",
    "remove_preset_confirm_tt": "Conferma rimozione pre-impostazioni",

    "rename_preset": "Rinomina",
    "rename_preset_tt": "Rinomina le pre-impostazioni selezionate",

    "add_preset": "Aggiungi",
    "add_preset_tt": "Aggiungi una nuova preimpostazione",

    "overwrite_preset": "Sostituisci",
    "overwrite_preset_tt": "Sovrascrivi la preimpostazione selezionata",

    "overwrite_preset_confirm": "Si",
    "overwrite_preset_confirm_tt": " Conferma sostituzione preimpostazione",

    "save_preset": "Salva",
    "save_preset_tt": "Salva le proprietà correnti come preset",


    # Simulate
    "simulation_scale":
        "Scala",
    "simulation_scale_tt":
        "Adatta una pre-impostazione a dive dimensioni dei rametti. "
        "Un rametto medio contiene uno o due anni di crescita ed è lungo circa 30cm. "
        "Una pre-impostazione è progettata per adattarsi a questa dimensione. Ma i modelli dei rametti posso essere di qualsiasi dimensione, "
        "da una singola foglia fino a diversi anni di crescita. "
        "Il modo in cui far coincidere un rametto di dimensioni diverse è quello di scalare semplicemente il modello del ramo. "
        "Questo mantiene i rametti alla stessa scala a grandezza naturale.",

    "simulation_flushes": "Cicli",
    "simulation_flushes_tt":
        "Numero di anni da aggiungere all'albero. "
        "Simula la crescita dell'albero in passi interattivi. "
        "Dopo ogni passo puoi guidare il tuo albero potandolo, "
        "eventualmente anche modificando i parametri o cambiando l'ambiente in cui cresce.",

    "zoom": "Zoom",
    "zoom_tt": "Zoom per inquadrare l'intero albero nella vista",

    "simulate": "Cresci",
    "simulate_tt":
        "Accresci l'albero in passi interattivi. "
        "Simula il passare delle stagioni accrescendo, flettendo, e potando l'albero in passi interattivi. "
        "Guarda il tuo albero evolversi anno per anno.",

    "restart": "Ricomincia",
    "restart_tt":
        "Rimuovi l'albero e ricomincia. "
        "Mettere a punto la forma del tuo albero è sovente un processo per tentativi. "
        "E anche quando i tuoi valori sono azzeccati, la natura non è perfetta. "
        "Cresci, metti a punto, ricomincia... questo è il modo per crescere un albero.",

    "manual_prune": "Pota",
    "manual_prune_tt":
        "Rimuovi i rami non voluti."
        "Lo strumento Pota taglia i rami in modo realistico, lo strumento Forma spunta i rami per permettere libertà artistica. "
        "\u2022 Disegna le linee di taglio nella vista 3d.",

    # Flow
    "favor_end": "Apicali",
    "favor_end_tt":
        "Favorisci la Dominanza apicale, offre alle estremità dei rami un vantaggio sui nuovi rami laterali. "
        "Crea rami laterali inizialmente più corti e meno forti, ma un vantaggio non è sempre una vittoria garantita. "
        "Favorisci i Soleggiati prende il sopravvento e lentamente aumenta le probabilità a favore dei rami con le migliori prestazioni -"
        "per permettere ai rami laterali corti di raggiungere o addirittura prendere il sopravvento come nuovo ramo principale. "
        "Favorisci la Dominanza e i Soleggiati sono due delle caratteristiche più importanti di un albero. "
        "Lavorano insieme per creare un ampio spettro di forme e caratteri",

    "favor_end_reduce": "Reduci", # TODO
    "favor_end_reduce_tt":
        "Reduce the effect of favor ends when the branch grows at an angle from vertical.",

    "favor_bright": "Illuminati",
    "favor_bright_tt":
        "Immaginate i rametti di un albero come migliaia di singole piante. "
        "Il luminoso diventa grande, il buio muore - questo se Favorisci i Soleggiati è al massimo. "
        "Ora collegate le piante con i rami - date loro un modo per condividere i loro guadagni. "
        "Quando lo zucchero scorre liberamente e la luce è abbondante, anche le piante in ombra avranno il sostegno necessario per crescere e trovare nuova luce",

    "favor_rising": "Verticali",
    "favor_rising_tt":
        "Favorisci i rami che crescono verso l'alto rispetto ai rami che penzolano verso il basso. "
        "Spingi in su i rami per ottenere un albero svettante. "
        "Un valore di 1 permette al ramo di aumentare finché il valore dei rami orizzontali sarà ridotto a zero. "
        "Se lo desideri puoi aumentare ancora questo valore.",

    # Drop
    "auto_prune_low": "Bassi",
    "auto_prune_low_tt":
        "Taglia i rami attaccati sotto questo questa altezza. "
        "Automaticamente pota la base dell'albero per permettere il libero passaggio di pedoni e mezzi. "
        "Lascia cadere i rami bassi danneggiati dalle gelate. O perdi i rami a causa degli animali alla ricerca di cibo. "
        "Questa potatura interviene gradualmente mentre l'albero cresce.",

    "auto_prune_keep_thick": "Più sottili",
    "auto_prune_keep_thick_tt":
        "Pota solo i rami più sottili, mantenendo quelli più spessi. "
        "Questo permetterà all'albero di crescere diversi grandi rami principali, dando al tuo albero un aspetto più naturale - "
        "un aspetto che i paesaggisti cercano quando potano alberi che hanno più spazio, come in un parco. "
        "Questa crescita accade anche in natura, dove gli animali che si nutrono preferiscono i rami freschi e succosi e lasciano quelli spessi.",

    "auto_prune_dangling": "Pendenti",
    "auto_prune_dangling_tt":
        "I rami appena al di sopra dell'altezza di autopotatura continuano a crescere ai lati e si piegano verso il basso con l'aumento della massa. "
        "Questi rami penzolanti possono essere lasciati crescere come in un salice piangente, oppure si possono potare a un'altezza stabilita.",

    # Drop
    "drop_shaded": "Ombreggiati",
    "drop_shaded_tt":
        "Fai cadere i rami in ombra. "
        "Ogni anno un albero produce moltissimi nuovi ramoscelli in ogni direzione. "
        "Questi piccoli ramoscelli sensibili rami esplorano lo spazio per cercare la luce. "
        "L'albero investirà energia solo nei ramoscelli illuminati e abbandonerà molti di quelli in ombra. "
        "Diminuisci il valore per mantenere più rametti, ottenendo un albero più denso. "
        "Aumenta verso uno per far cadere anche i luminosi, ottenendo un albero più trasparente e aperto.",

    "drop_obsolete": "Obsolete", # TODO
    "drop_obsolete_tt":
        "As the tree grows, lower branches get shaded and small branches drop. "
        "Old main branches will be thicker than needed to support their diminishing foliage. "
        "Unable to support this excess wood, the branch will eventually become obsolete, rot and drop. "
        "This also happens after heavy pruning.",

    "drop_decay": "Caduta Lenta",
    "drop_decay_tt":
        "Lascia i rami morti sull'albero. "
        "Passa del tempo prima che i rami morti marciscano e cadano dall'albero. Specialmente la parte inferiore "
        "delle conifere è piena di rami caduti.",

    "drop_weak": "Meno Vigorosi",
    "drop_weak_tt":
        "La potenza di crescita al di sotto della quale l'estremità di un ramo forma un fiore e smette di crescere in lunghezza. "
        "I rami ad alta potenza sono lì per far crescere l'albero a nuove altezze. "
        "Le estremità dei rami di potenza inferiore vengono riconvertite per formare fiori e frutti. "
        "Questo termina la crescita in lunghezza del ramo e permette ai rami laterali di prendere il sopravvento. "
        "Valori più alti aumenteranno le possibilità di fioritura. ",

    # Add
    "add_side_branches": "Gemme",
    "add_side_branches_tt":
        "Il numero di gemme per nodo influenza direttamente la disposizione geometrica dei rami, con schemi "
        "alternati, opposti e verticillati corrispondenti rispettivamente a una, due e da tre a sei gemme. "
        "Il vigore di crescita insieme alla probabilità determina quante di queste gemme si svilupperanno effettivamente in nuovi rami.",

    "add_chance": "Probabilità",
    "add_chance_tt":
        "Probabilità che un nodo giovane crei un nuovo ramo. "
        "Non tutte le gemme si aprono e sviluppano un nuovo ramo. "
        "Alcune sono danneggiate dal gelo o dagli insetti, altre sono soffocate dalla dominanza apicale.",

    "add_bud_life": "Vita della Gemma",
    "add_bud_life_tt":
        "Nella maggior parte delle specie, la gemma sopravvive solo un paio di anni. "
        "Le gemme fino a questa età sono vitali e possono far germogliare un nuovo ramoscello."
        "In altre specie, quasi tutti i germogli si aprono e formano ramoscelli molto corti, limitati dalla dominanza apicale. "
        "La maggior parte di questi germogli non sopravvivono mentre alcuni riescono a superare l'inibizione e a crescere in nuovi rami.",

    "add_only_on_end": "Solo nei Nodi Finali",
    "add_only_on_end_tt":
        "Aggiungi rami solo nei nodi finali. "
        "Gli alberi come le conifere sopprimono la crescita laterale con gli ormoni. "
        "In pratica significa che solo i nodi che sono molto vicini alla fine sono primi di ormoni e sono in grado di "
        "formare nuovi rami.",

    "add_regenerate": "Rigenerativi", # TODO
    "add_regenerate_tt":
        "I rami rigenerativi si formano immediatamente dopo una potatura severa o un danno naturale lungo il ramo. "
        "Con meno foglie da sostenere, l'eccesso di energia nel legno stimola la crescita di nuovi germogli, "
        "che servono a riparare l'albero e a riempire gli spazi vuoti. "
        "Non tutti gli alberi sono in grado di generare germogli rigenerativi, come accade per la maggior parte delle conifere. "
        "Per questo motivo, queste specie non rispondono bene alla potatura.",

    "add_fork": "Biforcazione",
    "add_fork_tt":
        "Quando un ramo è particolarmente forte e cresce vigoroso, può sviluppare diverse gemme vicino alla fine che possono sopraffare il germoglio finale. "
        "Il ramo si divide poi in diversi rami di pari potenza. Senza un ramo dominante al centro per spingerli ai lati, "
        "i rami che si biforcano crescono a metà dell'angolo regolare. Invece di formare un unico tronco ben distinto, un albero biforcuto crea una struttura di diffusione di rami principali.",

    "add_horizontal": "Orizzontale", #Phillotaxis angle is "indice fillotassico" or "angolo di divergenza" or just "divergenza"
    "add_horizontal_tt":
        "Ruota l'angolo di divergenza verso un orientamento orizzontale.",

    "add_angle": "Divergenza",
    "add_angle_tt":
        "Angolo fra un ramo e il suo genitore. "
        "Gli angoli compresi fra 0 e 90 gradi indicano rispettivamente una continuazione diritta del ramo "
        " o una direzione perpendicolare rispetto al ramo principale.",

    "add_twist": "Ruota",
    "add_twist_tt":
        "Ruota ogni nodo successivo. "
        "Specie come l'ippocastano hanno una torsione molto visibile lungo la lunghezza di loro rami, "
        "chiaramente visibile dal disegno della corteccia che si attorciglia attorno al tronco. "
        "Oltre l'ovvia qualità visiva, la rotazione si aggiunge anche all'indice fillotassico delle gemme. "
        "Questo migliora la distribuzione dei rami sugli alberi con ramificazioni opposte.",

    "add_up": "Su", #Guida verso l'alto i germogli
    "add_up_tt":
        "Gravitropismo negativo per le gemme - guida i nuovi germogli verso l'alto e in direzione contraria alla gravità. "
        "Usa valori negativi per guidare la crescita verso il basso.",

    # Grow
    "grow_length": "Lunghezza",
    "grow_length_tt": "Lunghezza totale della nuova crescita",

    "grow_nodes": "Nodi",
    "grow_nodes_tt":
        "Massimo numero di nodi che un ramo può sviluppare ogni anno. I rami deboli sviluppano meno nodi.",


    # Turn
    "turn_up": "Su", #Guida verso l'alto
    "turn_up_tt":
        "Gravitropismo negativo. Guida la nuova crescita verso l'alto e in direzione contraria alla gravità. "
        "Usa valori negativi per guidare la crescita verso il basso.",

    "turn_up_in_shade": "Su all'ombra",
    "turn_up_in_shade_tt":
        "Guida la crescita delle parti in ombra verso l'alto e in direzione contraria alla gravità. "
        "Usa valori negativi per guidare la crescita verso il basso.",

    "turn_to_light": "Verso la Luce",
    "turn_to_light_tt":
        "Fototropismo. Direziona la crescita verso la luce. "
        "Questa è l'effetto che fa crescere verso una finestra una pianta di appartamento. "
        "In un albero questo effetto migliora la distribuzione dei rami.",

    "turn_to_horizon": "Orizzontale",
    "turn_to_horizon_tt":
        "Quando un ramo è in ombra orienta la crescita del ramo verso il piano orizzontale.",


    # Interact
    "react_block_object": "Blocca",
    "react_block_object_tt":
        "Ferma la crescita dopo aver urtato l'oggetto contesto.",

    "react_shade_object": "Ombreggia",
    "react_shade_object_tt":
        "L'oggetto contesto influenzano i parametri che dipendono dalla luce. ",

    "react_deflect_object": "Devia",
    "react_deflect_object_tt": "Evita l'oggetto contesto.",

    "react_attract_object": "Attrai",
    "react_attract_object_tt":
        "Cresci verso l'oggetto contesto. "
        "I rametti possso liberamente crescere attraverso l'oggetto.",

    "react_vigor_object": "Potenza",
    "react_vigor_object_tt":
        "Seleziona un oggetto che controlli il vigore della nuova crescita.",

    "react_force": "Intensità",
    "react_force_tt":
        "Intensità della forza che l'oggetto esercita sull'albero.",

    "react_falloff": "Decadimento",
    "react_falloff_tt":
        "L'effetto è più forte vicino all'oggetto e diminuisce esponenzialmente con la distanza dall'oggetto.",


    # Thicken
    "thicken_tips": "Punte",
    "thicken_tips_tt":
        "Diametro della punta dei rami. "
        "Questo è lo spessore delle punte quando il ramo è al massimo della forza. "
        "Rami deboli possono ridurre questo valore.",

    "thicken_tips_reduce": "Reduci",
    "thicken_tips_reduce_tt":
        "Diminuisce lo spessore delle punte dei rami deboli. "
        "Rami deboli crescono più sottili. "
        "Questo impatta sulla forma dell'albero perché i rami fini si flettono maggiormente. "
        "Soprattutto sulle conifere pendenti che sopprimono notevolmente i loro rami laterali.",

    # TODO: Update the tooltip!
    "thicken_join": "Accrescimento",  # Grow or Merge or Join or Reinforce
    "thicken_join_tt":
        "Unisci rami per crescere in spessore. "
        "Lo spessore è aggiunto cominciando dalla punta. "
        "Ogni volta che si uniscono due rami, si sommano le loro sezioni per creare un ramo più spesso e più forte. "
        "Questo continua fino alla base dell'albero. "
        "Cambiare la velocità con cui un ramo cresce di spessore cambierà notevolmente la forma dell'albero.. "
        "Lo spessore aggiunto rinforza i rami e diminuisce la flessione.",

    "thicken_deadwood": "Legno Morto",
    "thicken_deadwood_tt":
        "Questo parametro si basa sul modello dei fasci vascolari. Quando i rami cadono, i loro fasci muoiono e questa "
        "area di legno morto fa parte della superficie totale della sezione trasversale. ",

    "thicken_base_scale": "Scala della Base",
    "thicken_base_scale_tt":
        "Aumenta lo spessore alla base del tronco dovuto dalla crescita delle radici.",

    "thicken_base_shape": "Forma",
    "thicken_base_shape_tt":
        "Regola la forma dell'inserimento della scala della base nel tronco.",

    "thicken_base_buttress": "Gobbe delle Radici",
    "thicken_base_buttress_tt":
        "Moltiplica le gobbe delle radici con la scala della base.",

    "root_distribution": "Distribuzione",
    "root_distribution_tt":
        "Distribuzione della scala della base sul tronco.",
    
    "roots": "Radici",
    "roots_tt":
        "Genera radici superficiali. "
        "Le radici normalmente crescono sotto terra, ma possono essere esposte dall'erosione del suolo. "
        "Esteticamente gradevoli, le radici superficiali ancorano l'albero al terreno.",
    
    "roots_roots_panel": "Radici",
    "roots_number": "Numero",
    "roots_number_tt": "Numero di radici principali",
    "roots_nodes": "Nodi",
    "roots_nodes_tt": "Numero di nodi per radice",
    "roots_length": "Lunghezza",
    "roots_length_tt": "Lunghezza tra due nodi.",
    "roots_climb": "Risalita",
    "roots_climb_tt": "Fai risalire le radici lungo il tronco per creare una fusione omogenea.",
    "roots_turn_down": "Cresci in basso",
    "roots_turn_down_tt": "Direzione iniziale verso il basso.",
    
    "roots_branches_panel": "Radici laterali",
    "roots_branches_panel_tt": "",
    "roots_generations": "Generazioni",
    "roots_generations_tt": "Aggiungi ulteriori generazioni di crescita per espandere il sistema radicale con maggiori dettagli.",
    "roots_density": "Densità",
    "roots_density_tt":
        "Probabilità di crescita di una radice laterale. Per aumentare ulteriormente la densità, "
        "aumenta il numero di nodi e riduci la lunghezza tra i nodi.",
    "roots_add_angle": "Angolo",
    "roots_add_angle_tt": "L'angolo rispetto alla radice principale.",
    "roots_add_down": "Aggiungi verso il basso",
    "roots_add_down_tt": "Le nuove radici iniziano con una direzione verso il basso.",
    
    "roots_variation_panel": "Casuale",
    "roots_random_heading": "Direzione",
    "roots_random_heading_tt": "Striscia sul terreno.",
    "roots_random_pitch": "Inclinazione",
    "roots_random_pitch_tt": "Gira verso l'alto e verso il basso durante la crescita.",
    "roots_random_seed": "Seme",
    "roots_random_seed_tt": "Ottieni una variazione casuale diversa.",
    
    "roots_thickness_panel": "Spessore",
    "roots_thickness": "Spessore",
    "roots_thickness_tt": "Spessore medio di una radice principale.",
    "roots_thickness_reduce": "Riduzione",
    "roots_thickness_reduce_tt": "Riduci lo spessore delle radici laterali.",
    "roots_thickness_random": "Casuale",
    "roots_thickness_random_tt": "Rendi casuale lo spessore di ogni radice.",
    
    "roots_terrain_panel": "Terreno",
    "roots_terrain_panel_tt": "",
    "roots_drop": "Proietta",
    "roots_drop_tt": "Proietta le radici sul terreno.",


    # Bend
    "bend_mass": "Massa",
    "bend_mass_tt":
        "Quantità di flessione a causa del peso del ramo. "
        "La curvatura dei rami ha un impatto significativo sulla forma degli alberi, soprattutto quando invecchiano. "
        "Quanto ogni ramo si piega dipende dal suo spessore - "
        "I rami più spessi pesano di più, ma la loro maggiore sezione trasversale li rende esponenzialmente più forti nella lotta contro la gravità.",

    "bend_twig_mass": "Massa di Rametti",
    "bend_twig_mass_tt":
        "Quantità di flessione in relazione al peso delle foglie. "
        "Le estremità dei rami portano il peso relativamente pesante dei loro ramoscelli pieni di foglie, fiori e frutti. "
        "Gli alberi cercano di contrastarne la flessione crescendo verso l'alto con un gravitropismo negativo. "
        "L'interazione fra il piegamento o il gravitropismo gioca un ruolo importante nella formazione di un carattere florido o piangente.",

    "bend_twig_mass_solidify": "Solidifica",
    "bend_twig_mass_solidify_tt":
        "Solidifica la flessione causata dal peso esercitato sulle estremità dei rami. "
        "Questo peso varia con le stagioni, i fiori primaverili pesanti, le foglie grandi e i frutti grossi spingono il ramo verso il basso. "
        "Tuttavia, quando arriva il momento in cui il ramo si irrigidisce, la maggior parte di questo peso può già essere stato abbandonato. "
        "Pertanto questo parametro è sovente inferiore a quello usato per solidificare il peso del ramo.",

    "bend_reaction": "Su",
    "bend_reaction_tt":
        "Il legno di reazione consente ai rami che crescono rapidamente in spessore di piegarsi attivamente verso l'alto nel tempo. "
        "L'effetto si intensifica man mano che il ramo si allontana ulteriormente da una direzione di crescita verticale. "
        "Gli alberi inclinati possono tornare alla verticale, e i rami laterali vigorosi possono prendere il posto del nuovo leader.",

    # Shade
    "shade_area": "Superficie Fogliare",
    "shade_area_tt":
        "Superficie della fogliame combinato all'estremità di ogni ramo, in dm² (10cm x 10cm)."
        "Le foglie situate nella parte alta della chioma dell'albero proietteranno ombra sulle ramificazioni più in basso.",

    "shade_area_reduce": "Reduci",
    "shade_area_reduce_tt":
        "Riduci l'area fogliare sui rami meno vigorosi.",

    "shade_area_depth": "Profondità",
    "shade_area_depth_tt":
        "Aumenta l'ombreggiatura ai lati per dare più profondità alla forma. "
        "Questo causerà più ombra dai lati dell'albero, "
        "e più ombra in generale. Quindi assicuratevi di compensare riducendo la caduta delle parti in ombra. "
        "Abilitare l'anteprima dell'ombra per vedere l'effetto.",

    "tweak": "Regolate",
    "tweak_tt": "Regolate questi parametri nella vista, con una visualizzazione 3D delle modifiche.",

    "shade_leaf_sides": "Sides",
    "shade_leaf_sides_tt":
        "Also distribute shadow casting leaf areas along the sides of branches. "
        "Most trees can be simulated with just the leaves at the branch tips, a small abstraction that works well. "
        "But on trees with weeping branches, side twigs are needed. Do note that you need a smaller leaf area with this, "
        "because more twigs will be placed.",


    # Build
    "build_resolution": "Risoluzione",
    "build_resolution_tt":
        "Il numero di vertici alla base dell'albero, dove è maggiore il suo spessore.",

    "build_resolution_reduce": "Riduzione",
    "build_resolution_reduce_tt":
        "Riduce i poligoni nei rami fini. "
        "La maggior parte di poligoni sono nelle migliaia di giovani rami. "
        "Questi ramoscelli possono avere pochi poligoni senza perdere qualità visiva.",

    "smooth": "Smussa",
    "smooth_tt":
        "Riduce l'angolo degli angoli vivi per creare curvature più morbide. ",

    "texture_bark": "Corteccia",
    "texture_bark_tt":
        "Scegli una texture",

    "texture_repeat": "Ripetizione UV",
    "texture_repeat_tt":
        "Numero di volte in cui la texture della corteccia si ripete attorno alla circonferenza della base dell'albero - "
        "ridotta automaticamente sui rami più sottili.",


    # Wind
    "calculate_wind": "Anima Vento",
    "calculate_wind_tt": "Calcola l'animazione del vento",

    "wind_breeze": "Brezza",
    "wind_breeze_tt":
        "Rendi vivaci i ramoscelli grazie all'animazione di una brezza leggera. "
        "Puoi combinarla con l'animazione del vento regolare per una maggiore deformazione.",

    "turbulence": "Turbulenza",
    "turbulence_tt":
        "Turbolenza del vento - l'aria che si muove tra gli alberi solleva le foglie e fa agitare i rami nel vento.",

    "wind_shapes": "Chiavi di Forma",
    "wind_shapes_tt":
        "Numero di forme del vento da creare. "
        "Le forme del vento calcolate come chiavi di forma. "
        "Ogni forma è 2 frame dalle altre e si interpola fluidamente con le forme precedenti e successive. "
        "Moltiplica per 2 per ottenere la lunghezza totale dell'animazione del vento. "
        "In seguito, il vento viene ripetuto all'infinito. "
        "Quando si esporta in Alembic, ricorda di impostare il corretto intervallo di frame per la ripetizioe.",


    # Twigs
    "twig_menu": "Rametti",  # Twigs, Library, Pick
    "twig_menu_tt":
        "Scegli un set di rametti per aggiungerli all'albero. "
        "Il selezionatore di rametti elenca ogni rametto trovato nella cartella rametti - "
        "puoi scegliere una cartella nelle preferenze di Grove."
        "Puoi anche scegliere oggetti direttamente da questa scena.",

    "twig_pick_objects": "Oggetto della scena", # "scegli oggetto scena" o "oggetti scena" ?
    "twig_pick_objects_tt": "Scegli qualsiasi oggetto 3D nella scena.",

    "twig_no_twigs": "Senza Rametti",
    "twig_no_twigs_tt": "Senza Rametti",

    "twig_object_end": "Lunghi",
    "twig_object_end_tt":
        "Oggetti rametto da distribuire alla fine dei rami.",

    "twig_object_side": "Corti",
    "twig_object_side_tt":
        "Oggetti rametto da distribuire lungo i lati dei rami. "
        "I rametti laterali sono nuovi rami freschi che si sviluppano lungo i lati dei rami esistenti. "
        "Portano foglie, a volte fiori, in seguito frutta. "
        "I rametti laterali sono spesso più corti di quelli terminali a causa dalla soppresione ormonale del ramo principale che li ha creati."
        "Solo i più forti alla fine cresceranno in nuovi rami completi.",

    "twig_density": "Densità",
    "twig_density_tt":
        "Controlla la densità del fogliame del tuo albero aggiungendo più o meno rametti laterali.",

    "twig_view_detail": "Dettagli Vista",
    "twig_view_detail_tt":
        "Abbassa la risoluzione dei rametti. "
        "Per migliori prestazioni nella vista 3D, questo aggiunge un modificatore Decimazione a ogni modello di rametto. "
        "Le viste 3D usano il modello modificato, a bassa risoluzione - mentre il motore di rendering usa l'originale.",

    "twig_side_on_tips": "Laterali sulle estremità",
    "twig_side_on_tips_tt":
        "Distribuisci rametti laterali anche sulle estremità dei rami, in aggiunta ai rametti apicali."
        "Ricostruisci il tuo albero per vedere l'effetto",

    "twig_pick_collections": "Collezioni",
    "twig_pick_collections_tt": "Scegli una collezione di oggetti rametti nel file corrente.",

    "twig_hide": "",
    "twig_hide_tt": "Nascondi temporaneamente i rametti per avere una buona visione della struttura dei rami.",

    "twig_longevity": "Vita",
    "twig_longevity_tt":
        "Duplica i rametti laterali sui rami giovani verso la fine di ogni ramo. "
        "Aumenta per far apparire i rametti su rami sempre più vecchi e più spessi. "
        "Ricostruisci il tuo albero per vedere l'effetto",

    "twig_object_upward": "Verticali",
    "twig_object_upward_tt":
        "Modello di ramoscello opzionale che sovrascrive il ramoscello terminale quando cresce in modo ripido verso l'alto. "
        "Questi rametti sono spesso anche più lunghi e hanno le foglie che si attorcigliano in tutte le direzioni. "
        "Se non è impostato nessun ramoscello, verrà utilizzato invece il ramoscello terminale",

    "twig_object_dead": "Morti",
    "twig_object_dead_tt":
        "Modello di ramoscello opzionale che sovrascrive tutti gli altri, nel caso siano rametti morti. "
        "Se non viene impostato alcun ramoscello, non verrà utilizzato alcun ramoscello per i rametti morti, con conseguente perdita di dettaglio nelle aree a bassa potenza.",

    "twig_wither": "Appassiti",
    "twig_wither_tt":
        "Numero di anni (dopo la vita) in cui i rametti morti si attaccano e appassiscono sull'albero. "
        "Ricostruire per vedere l'effetto",

    "use_adaptive_units": "Imposta le Unità della Scena",
    "use_adaptive_units_tt":
        "Grove utilizza unità di misura per diversi suoi parametri, alcuni dei quali rappresentano piccole distanze. "
        "Con le unità adattive abilitate, 0,001m saranno visualizzati come 1mm.",

    "language": "Lingua",
    "language_tt": "Lingua da usare per l'interfaccia e i suggerimenti",


    "close_button": "",
    "close_button_tt": "Chiudi",
    "close": "Chiudi",


    # New
    "grove": "Grove",

    "label_direction": "Direzione Iniziale",

    "rebuild": "Ricostruisci",
    "rebuild_tt": "Ricostruisci il modello del tuo albero.",

    "add_new_grove": "Aggiungi Nuova Selva",
    "add_new_grove_tt": "Aggiungi una nuova raccolta di boschetti.",  # Here I need to translate in some way...

    "select_a_grove_collection": "Seleziona una collezione Grove.",

    "select_linked_branches_tt": "Espandi la selezione corrente all'intero ramo e i suoi figli.",
    "select_linked_branches": "Seleziona i rami collegati",

    "show_dead_preview": "Anteprima Rami Morti",

    "disable_outline": "Disabilita contorno",
    "disable_outline_tt": 
        "Disabilita l'ombreggiatura del contorno per una corretta rappresentazione dell'albero e per un migliore "
        "feedback visivo durante le modifiche. Il contorno fa apparire i rami molto più spessi di quanto non siano in realtà.",

    "set_background": "Sfondo luminoso",
    "set_background_tt":
        "Schiarisci lo sfondo della finestra di viewport impostandolo sul grigio medio."
        "I rami degli alberi saranno molto più facili da vedere e gli alberi saranno più belli.",

    # Record
    "record_enabled": "Registra",
    "record_enabled_tt":
        "Registra la crescita come sequenza di oggetti in una collezione dedicata chiamata 'Record'. "
        "Ogni passo è impostato per la visibilità solo per un breve periodo di tempo. Tutti questi elementi in sequenza formano l'animazione della vostra crescita.",

    "record_start": "Primo Fotogramma",
    "record_start_tt":
        "Sposta l'animazione in avanti nel tempo per iniziare a questo frame.",

    "record_interval": "Intervallo",
    "record_interval_tt":
        "Ogni anno è una dolce interpolazione dalla forma primaverile iniziale a quella, pianamente sviluppata, estiva. "
        "Definisci il numero di fotogrammi per l'interpolazione e, attraverso questo, la velocità di crescita. Puoi modificare questo valore in ogni momento, "
        "la tua animazione sarà aggiornata all'istante",

    "regrow": "Ricresci",
    "regrow_tt":
        "Riavvia e fai ricrescere rapidamente gli alberi fino all'età attuale - saltando le fasi di sviluppo, "
        "ma anche le fasi di crescita interattive e le occasioni di potatura.",

    "replant_grove": "Ripianta",
    "replant_grove_tt": "Ripianta.",

    "label_animating_wind": "Calcolo vento...",
    "label_stop": "Ferma",

    "import_preset": "Importa  un Predefinito...",
    "import_preset_tt": "Un preset è memorizzato in un file .seed.json che potete condividere con altri - importane  uno per aggiungerlo alla lista di preset.",

    "placeholder_delay": "Ritardo",
    "placeholder_delay_tt": "Anni di attesa prima di iniziare a crescere",

    "add_tree": "Pianta",
    "add_tree_tt":
        "Aggiungi un oggetto vuoto dal quale far nascere. "
        "Sposta, ruota, duplica o cancella questo oggetto per far crescere più alberi da posizioni o angoli specifici, anche in gruppi.",

    "prune_status_draw_lines": "Disegna linee di taglio",
    "prune_status_do_prune": "Pota",

    # Manual bend
    "manual_bend": "Piega",
    "manual_bend_tt":
        "Strumento ispirato alla tecnica Bonsai per piegare i rami con filo metallico, ma molto più flessibile - "
        "puoi piegare qualsiasi ramo, indipendentemente dal suo spessore, senza il timore di spezzarlo. "
        "La tecnica del Bonsai è applicabile solamente a piccoli alberi: usa lo stesso principio per dare forma ad alberi di ogni grandezza.",
    
    "bend_tool_distance": "Distanza",
    "bend_tool_distance_tt": "Lunghezza",
    
    "bend_tool_bend_button": "Piega",
    "bend_tool_bend_button_tt": "Spazio",
    
    "bend_tool_curve": "Curva",
    "bend_tool_curve_tt": "Forma della curva",
    "bend_tool_curve_simple": "Semplice",
    "bend_tool_curve_flexible": "Flessibile",
    "bend_tool_curve_s_curve": "Curva a S",

    "old_release_warning_line_1": "Alberi creati con una vecchia versione.",
    "old_release_warning_line_2": "Molto è cambiato.",
    "old_release_warning_line_3": "Usa la vecchia versione per editarli.",

    # Stake
    "stake_enabled": "Estaca",
    "stake_enabled_tt": "Una estaca aiuta il tronco a crescere dritto.",
    "stake_height": "Altezza",
    "stake_height_tt": "Fino a questa altezza, l'estaca impedisce all'albero di piegarsi, favorendone la crescita dritta.",

    # File
    'file': "File",
    "file_tt": "Importa ed esporta i tuoi alberi da e verso file .grove. Salva e recupera i tuoi alberi.",

    "file_recent": "File recenti",

    "file_import": "Importa alberi",
    "file_import_tt": "Importa una simulazione da un file .grove.",

    "file_export": "Esporta alberi",
    "file_export_tt": "Esporta l'attuale simulazione in un file .grove.",

    # Old and unused
    "shade_sensitivity": "Sensibilità",
    "shade_sensitivity_tt":
        "Sensibilità all'ombraggiatura. "
        "L'ombreggiatura è un valore lineare dalla luce all'ombra ma i processi naturali sovente rispondono in maniera esponenziale. "
        "Setta il valore su 0 per una lenta risposta all'ombra, un ramo reagirà solo dopo che una parte significativa rimarrà in ombra. "
        "Setta il valore su 1 per una reazione immediata, la più tenue parte di ombra viene percepita in modo notevole.",

    "shade_elongation": "Allungamento per Ombreggiatura",
    "shade_elongation_tt":
        "I rami ombreggiati possono essere più lunghi o più corti. "
        "Le piante che crescono all'ombra crescono di più per trovare la luce. "
        "Questo produce rami più fini e più deboli che si piegano di più. "
        "Si notano rami a penzoloni alla base della chioma.",

    "wind_frequency": "Frequenza del Vento",
    "wind_frequency_tt":
        "Frequenza del Vento.",

    "shade_avoidance": "Evita l'Ombra",
    "shade_avoidance_tt":
        "Incrementa o decrementa Favorisci la Dominanza sui rami in ombra. "
        "Evitando l'ombra ogni ramo controlla la sua dominanza, utilizzandola come una strategia per cercare la luce. "
        "Più un ramo è ombreggiato, più può favorire la sua attuale crescita alla ricerca della luce, "
        "oppure può favorire la crescita dei rami secondari per assorbire quanta più luce possibile all'ombra. "
        "Quest'ultima possibilità si può vedere in specie del fondo forestale come il Faggio e la Nocciola.",

    "label_layers": "Livelli",

    "branching_inefficiency": "Inefficienza",
    "branching_inefficiency_tt":
        "Un modo diretto per limitare la crescita di rami secondari i conseguenti figli. "
        "L'attacco fra rami è imperfetto e limita il trasporto di acqua.",

    "sapwood": "Alburno",
    "sapwood_tt":
        "Spessore del legno vivo. Questa è la parte che trasporta la linfa. L'interno dei rami, "
        "legno morto che svolge solo funzioni di supporto, è chiamato durame. Aumentando "
        "questo valore causa un minor ispessimento sui rami più spessi.",

    "sow_enabled": "Seminare",
    "sow_enabled_tt": "Spargere semi attorno agli alberi esistenti e più vecchi per simulare un bosco di alberi che si diffonde naturalmente.",
    
    "sow_age": "Ritardo",
    "sow_age_tt": "Gli alberi impiegano diversi anni a radicarsi e stabilire uno stato energetico positivo prima di iniziare a produrre semi.",
    
    "sow_chance": "Probabilità",
    "sow_chance_tt":
        "La probabilità annuale che ogni albero crei un discendente di successo."
        "In realtà, alcuni alberi possono creare migliaia di semi, e centinaia di questi semi possono germinare ogni anno."
        "Ma quasi nessuno sopravvive per crescere come un albero adeguato."
        "Per mantenere la simulazione a una velocità utilizzabile, mantieni bassa la probabilità.",
    
    "sow_distance": "Distanza",
    "sow_distance_tt": "I semi vengono dispersi entro una distanza attorno agli alberi esistenti.",
    
    "sow_limit": "Limite",
    "sow_limit_tt": "Il numero massimo di alberi. Smette di aggiungere nuovi alberi oltre questo numero per mantenere la simulazione a una velocità utilizzabile.",
    
    "build_skeleton": "Costruisci scheletro",
    "build_skeleton_tt":
        "Crea ossa, gruppi di pesi e animazione del vento.",
    
    "skeleton": "Scheletro",
    "skeleton_tt":
        "Crea uno scheletro che ti permette di animare gli alberi usando le ossa. "
        "Aggiunge anche gruppi di vertici per collegare i punti della mesh alle rispettive ossa. "
        "Opzionalmente, aggiunge animazione del vento alle nuove ossa.",
    
    "skeleton_panel_bones": "Ossa",
    "skeleton_panel_wind": "Vento",
    
    "skeleton_reduce": "Riduci",
    "skeleton_reduce_tt":
        "Crea meno ossa saltando i rami laterali sottili.",
    
    "skeleton_bias": "Distribuzione",
    "skeleton_bias_tt":
        "Aumenta per aggiungere più ossa nella parte superiore, diminuisci per aggiungere più ossa nella parte inferiore.",
    
    "skeleton_length": "Lunghezza",
    "skeleton_length_tt":
        "Crea ossa più lunghe saltando i nodi.",
    
    "skeleton_connected": "Connesso",
    "skeleton_connected_tt":
        "Blender può costruire una gerarchia da ossa fluttuanti, mentre alcuni altri programmi richiedono una catena connessa di ossa. "
        "Le connessioni richiedono una nuova osso ad ogni punto di ramificazione, aumentando il numero di ossa.",
    
    # These are new features that need Italian translations
    
    "shade_branches": "Rami",
    "shade_branches_tt": "La maggior parte dell'ombra proviene dalle foglie, e per alcuni alberi puoi includere anche la geometria dei rami nel calcolo dell'ombra.",
    
    "shade_alongside": "Lungo i lati",
    "shade_alongside_tt": "Oltre ai rametti appena cresciuti, alberi come i pini hanno vecchi aghi lungo i loro rami.",
    
    "shade_alongside_diameter": "Diametro",
    "shade_alongside_diameter_tt": "Diametro della geometria che proietta ombra lungo i lati dei rami.",
    
    "shade_branches_panel": "Rami",
    "shade_leaves_panel": "Foglie",
    
    "auto_prune_enabled": "Potatura automatica",
    "auto_prune_enabled_tt": 
        "Potatura automatica annuale dei rami laterali che libera la base dell'albero. "
        "Questo fornisce una vista chiara e consente il libero passaggio di persone e traffico. "
        "Rimuove i rami bassi danneggiati dal gelo al suolo. E perde rami a causa degli animali che si nutrono. "
        "Questa potatura viene eseguita automaticamente ogni anno.",
    
    "panel_build_mesh": "Dettaglio",
    
    "widget_scale": "Scala dell'interfaccia",
    "widget_scale_tt": 
        "Regola la dimensione dei widget dell'interfaccia se appaiono troppo piccoli o grandi sul tuo schermo.",
    
    "grow_together": "Cresci insieme",
    "grow_together_tt_short": "Fai crescere tutte le collezioni Grove insieme come una sola.\nMescola specie e lasciale competere per la luce.",
    "grow_together_tt":
        "Fai crescere tutte le collezioni Grove separate insieme come una sola, così puoi mescolare diverse specie di alberi. "
        "Con calcoli combinati di ombra e fototropismo per farli competere per la luce.",
    
    "restart_all": "Riavvia tutto",
    "restart_all_tt": "Riavvia ogni collezione Grove.",
    
    "plant": "Pianta",
    "plant_tt":
        "Pianta un gruppo di alberi - crea frutteti, siepi o isole naturali di alberi. "
        "Questo strumento crea oggetti vuoti, che puoi spostare liberamente, duplicare o eliminare.",
    
    "plant_layout": "Disposizione",
    "plant_layout_tt": "Pianta un frutteto, una piantagione, una siepe, un anello o gruppi naturali di alberi",
    
    "plant_trees": "Alberi",
    "plant_trees_tt": "Numero di alberi",
    
    "plant_space": "Spazio",
    "plant_space_tt": "Distanza tra gli alberi",
    
    "plant_random_shift": "Spostamento casuale",
    "plant_random_shift_tt": "Posizionamento irregolare",
    
    "plant_random_seed": "Seme casuale",
    "plant_random_seed_tt": "Varia lo spostamento casuale",
    
    "plant_delay": "Ritardo",
    "plant_delay_tt": "Gli alberi lontani dal centro iniziano a crescere in un anno successivo.",
    
    "plant_ring_radius": "Raggio",
    "plant_ring_radius_tt": "Distanza dal centro dell'anello",
    
    "plant_rows_trees_tt": "Numero di alberi per fila",
    
    "plant_rows": "File",
    "plant_rows_tt": "Numero di file",
    
    "plant_rows_space": "Spazio",
    "plant_rows_space_tt": "Spazio tra le file",
    
    "plant_rows_diagonal": "Diagonale",
    "plant_rows_diagonal_tt": "Sposta ogni seconda fila per ottenere un pattern a diamante",
    
    "plant_islands_trees_tt": "Numero medio di alberi per isola",
    
    "plant_islands": "Isole",
    "plant_islands_tt": "Numero di isole di alberi",
    
    "plant_islands_space": "Spazio isole",
    "plant_islands_space_tt": "Distanza media tra le isole di alberi",
    
    "plant_islands_clearing": "Radura",
    "plant_islands_clearing_tt": "Spazio aperto nel mezzo",
    
    "plant_islands_randomize": "Casuale",
    "plant_islands_randomize_tt": "Varia il numero di alberi per isola",
    
    "plant_layout_clump": "Gruppo",
    "plant_layout_rows": "File",
    "plant_layout_ring": "Anello",
    "plant_layout_islands": "Isole",
    
    "plant_variation_panel": "Variazione",
    "plant_diverge": "Divergenza",
    "plant_diverge_tt": "Devia la direzione di crescita dagli alberi vicini.",
    
    "plant_terrain_panel": "Terreno",
    "plant_terrain_drop": "Proietta",
    "plant_terrain_drop_tt": "Proietta gli alberi sul terreno.",
    
    "plant_terrain_slope": "Pendenza",
    "plant_terrain_slope_tt": "Adotta la pendenza del paesaggio nella rotazione.",
    
    "surround_enabled": "Circonda",
    "surround_enabled_tt":
        "Circonda i tuoi alberi con ombra da tutti i lati. "
        "Questo farà crescere gli alberi più alti e perderanno più rami inferiori. "
        "Ti permette di far crescere alberi che assomigliano a quelli trovati in una foresta, senza dover far crescere un'intera foresta.",
    
    "surround_density": "Densità",
    "surround_density_tt":
        "Cresci in un campo aperto o in una foresta densa, o qualsiasi cosa intermedia.",
    
    "surround_height": "Altezza",
    "surround_height_tt":
        "Un'altezza fissa che può essere usata per alberi già stabiliti o edifici. "
        "Usa l'altezza automatica per far crescere l'ambiente circostante insieme ai tuoi alberi.",
    
    "surround_grow": "Crescita",
    "surround_grow_tt":
        "Aumenta automaticamente l'altezza ogni anno - gli alberi circostanti crescono insieme ai tuoi alberi.",
    
    "surround_distance": "Distanza",
    "surround_distance_tt": "Spazio libero in cui crescere.",
    
    "turn_random": "Casuale",
    "turn_random_tt":
        "Il ramo è libero di muoversi in direzioni casuali e incontrollate - non guidato dalla luce o dalla gravità.",
    
    "build_triangulate": "Triangolare",
    "build_triangulate_tt": 
        "Usa solo triangoli per costruire i rami dell'albero, niente quadrilateri.",
        
    "build_cutoff_thickness": "Taglio per spessore",
    "build_cutoff_thickness_tt": 
        "Salta la costruzione di nodi al di sotto di questo diametro per ridurre drasticamente il numero di poligoni. "
        "Compensa con rametti più grandi che rappresentano più anni di crescita.",
        
    "build_cutoff_age": "Taglio per età",
    "build_cutoff_age_tt": 
        "Salta la costruzione degli ultimi anni di crescita per ridurre drasticamente il numero di poligoni. "
        "Compensa con rametti più grandi che rappresentano più anni di crescita.",
        
    "build_blend": "Connessioni fluide",
    "build_blend_tt": 
        "Aggiungi nodi aggiuntivi per creare una transizione fluida dal ramo principale. "
        "Questo è visivamente importante per i rami più spessi, ma può essere disabilitato per i rami più sottili "
        "per ridurre drasticamente il numero di poligoni.",
        
    "build_end_cap": "Chiusure terminali",
    "build_end_cap_tt": 
        "Chiudi le estremità aperte dei rami con geometria aggiuntiva, o salta questo passaggio per i rami più sottili "
        "per ridurre significativamente il numero di poligoni. "
        "A seconda della distanza dall'albero e se l'albero è in foglie o meno, "
        "le estremità più sottili possono essere comunque quasi invisibili.",
        
    "detail_simplify": "Semplifica",
    "detail_simplify_tt": 
        "Semplifica i rami saltando i nodi diritti con quasi nessun cambiamento di direzione. "
        "Questo fornisce solo una modesta riduzione del numero di poligoni.",
    
    "presets_path": "Cartella Preimpostazioni",
    "presets_path_tt": 
        "Seleziona la cartella dove salvi le preimpostazioni. Tutte le preimpostazioni in questa cartella appariranno nel selettore di preimpostazioni.",
    
    "use_scientific_names": "Usa Nomi Scientifici",
    "use_scientific_names_tt": 
        "Visualizza le specie di rametti usando i loro nomi scientifici, quando disponibili. "
        "Quando disattivato, il menu dei rametti mostra il nome comune in inglese.",
    
    "react_enabled": "Reagisci",
    "react_enabled_tt": 
        "Usa oggetti mesh per attirare, deviare o interrompere la nuova crescita. "
        "Fai in modo che un edificio proietti ombra, o sii creativo e fai crescere alberi all'interno di forme.",
    
    "add_chance_reduce": "Riduzione",
    "add_chance_reduce_tt": 
        "Riduci la probabilità di aggiungere rami laterali ai rami meno vigorosi. "
        "Aggiungendo meno rami laterali, questi rami accumuleranno meno spessore, "
        "e i rami più sottili si piegheranno di più sotto l'effetto della gravità.",
    
    "add_planar": "Planare",
    "add_planar_tt": 
        "Simile alla rotazione orizzontale, ma ora i nuovi rami germogliano in modo planare rispetto alla direzione di crescita.",
    
    "select_thicker": "Seleziona più spessi",
    "select_thicker_tt": 
        "Seleziona la geometria che appartiene ai nodi di rami più spessi, usando l'attributo 'Spessore'.",
    "select_thicker_threshold": "Soglia",
    
    "restart_revert": "Ricomincia da zero",
    "restart_revert_tt": 
        "Ripristina tutto ai valori predefiniti, ricarica la preimpostazione attiva e ricomincia con un singolo albero.",
    
    "restart_single_tree": "Albero singolo",
    "restart_single_tree_tt": 
        "Rimuovi i segnaposto e pianta un singolo albero all'origine.",
    
    "grow_tool_growing": "In crescita",
    "grow_tool_growing_tt": "Premi Esc per annullare.",
    
    "wind_turbulence": "Turbolenza",
    "wind_turbulence_tt": "Solleva i rametti e fa danzare i rami nel vento.",
    
    "wind_vector": "Vento",
    "wind_vector_tt": "Velocità e direzione",
    
    "escape_to_stop": "Esc per fermare",
    
    "turntable": "Vista",
    "turntable_tt": "Visualizzazione",
    
    "fallback_instructions": "Preparati a crescere",
    "fallback_instructions_tt": "Segui le istruzioni su http://www.thegrove3d.com/info/install/ per installare il nucleo di simulazione.",
    
    "trial_end": "Acquista Ora...",
    "trial_end_tt": "La tua prova è scaduta. Se ti piace The Grove, acquista una licenza per continuare a far crescere alberi straordinari.",
    
    "operator_turntable": "Vista",
    "operator_turntable_tt": "Visualizza i tuoi alberi a livello degli occhi - cammina intorno e sotto la chioma.",
    
    "draw": "Disegna",
    "draw_tt": "Fai crescere un nuovo ramo lungo un percorso.",
}
