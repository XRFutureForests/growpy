# coding=utf-8

dictionary = {

    "": "",

    # Panel titles
    "panel_presets": "Préréglage",
    "panel_twigs": "Rameaux",
    "panel_twigs_more": "Plus",
    "panel_simulation": "Simulation",
    "panel_react": "Réagis",
    "panel_favor": "Favoris",
    "panel_drop": "Laisse tomber",
    "panel_add": "Ajoute",
    "panel_grow": "Fais pousser",
    "panel_turn": "Tourne",
    "panel_thicken": "Épaissis",
    "panel_bend": "Ploie",
    "panel_shade": "Ombrage",
    "panel_build": "Construis",
    "panel_build_wind": "Vent",
    "panel_build_mesh": "Maillage",
    "panel_build_texture": "Texture",

    # User preferences
    "set_twigs_path": "Définis le dossier des rameaux...",
    "twigs_path": "Dossier des rameaux",
    "twigs_path_tt":
        "Indique le dossier où tu stockes les rameaux. "
        "Ces rameaux apparaîtront dans la sélection de rameaux.",
    "set_textures_path": "Définis le dossier des textures...",
    "textures_path": "Dossier des textures d'écorce",
    "textures_path_tt":
        "Indique le dossier où tu stockes les textures d'écorce. "
        "Ces textures apparaîtront dans la sélection de textures.",

    # Interface messages
    "remove_preset_info": "Supprimer {}?",
    "overwrite_preset_info": "Écraser {}?",
    "name_preset_info": "Nomme ton préréglage.",
    "height_info": "{:.1f} m",
    "age_info": "{} pousses",
    "branch_info": "{} branche",
    "branches_info": "{:,} branches",
    "polygons_info": "{:,} faces",
    "tips_info": "Lis les infobulles :",

    # Presets
    "presets_menu": "",
    "presets_menu_tt": "Charger les paramètres prédéfinis des espèces d'arbres",

    "preset_name": "Nouveau nom",
    "preset_name_tt": "Nom du préréglage à enregistrer ou à écraser",

    "remove_preset": "Supprimer",
    "remove_preset_tt": "Supprimer ce préréglage",

    "cancel_action": "Annuler",

    "remove_preset_confirm": "Supprimer",
    "remove_preset_confirm_tt": "Confirmer la suppression de ce préréglage",

    "rename_preset": "Renommer",
    "rename_preset_tt": "Renommer ce préréglage",

    "add_preset": "Ajouter",
    "add_preset_tt": "Ajouter un nouveau préréglage ou écraser le préréglage si le nom existe déjà.",

    "overwrite_preset": "Écraser",
    "overwrite_preset_tt": "Écraser ce préréglage",

    "overwrite_preset_confirm": "Écraser",
    "overwrite_preset_confirm_tt": "Confirmer le remplacement et l'écrasement de ce préréglage",

    "save_preset": "Enregistrer",
    "save_preset_tt": "Enregistrer les propriétés actuelles en tant que préréglage",


    # Simulate
    "simulation_flushes": "Pousses",
    "simulation_flushes_tt":
        "Nombre d'années ajoutées pour la croissance. "
        "Simule ton arbre par petites étapes interactives. "
        "Après chaque étape, tu peux guider ton arbre en l'élaguant, "
        "peut-être même en ajustant ses paramètres ou en changeant l'environnement dans lequel il pousse.",

    "zoom": "Zoom",
    "zoom_tt": "Double-clique pour te promener autour de tes arbres.",

    "simulate": "Faire pousser",
    "simulate_tt":
        "Fais pousser ton arbre. "
        "Simule les saisons en faisant pousser, tourner, plier, couler et laisser tomber des étapes interactives. "
        "Observe l'évolution de ton arbre année après année.",

    "restart": "Redémarrer",
    "restart_tt":
        "Ajuster le caractère de votre arbre nécessite des expérimentations. "
        "Faites pousser, ajustez, redémarrez, répétez... c'est la manière de faire pousser un arbre. "
        "Double-cliquez pour plus d'options.",

    "manual_prune": "Élaguer",
    "manual_prune_tt":
        "Dessinez des lignes de coupe pour enlever ou raccourcir les branches.",

    # Flow
    "favor_end": "Fin",
    "favor_end_tt":
        "Favoriser la fin donne aux extrémités des branches une longueur d'avance sur les nouvelles branches latérales. "
        "Cela crée des petites branches latérales moins vigoureuses au début, mais une longueur d'avance n'est pas toujours une victoire garantie. "
        "Favor Bright prend le relais et changera progressivement les chances en faveur des meilleures performeuses - "
        "pour permettre aux petites branches latérales de rattraper leur retard ou même de devenir la nouvelle branche principale. "
        "Favor Bright et Favor End sont deux des caractéristiques les plus importantes d'un arbre. "
        "Ils travaillent ensemble pour créer un large spectre de formes et de caractères.",

    "shade_avoidance": "Boost d'ombre",  # Escape Shade
    "shade_avoidance_tt":
        "Augmentez ou diminuez Favor End sur les branches ombragées. "
        "Chaque branche contrôle son propre Favor End, comme stratégie pour trouver la lumière. "
        "Plus une branche est ombragée, elle peut soit favoriser la croissance de sa pointe pour échapper à l'ombre, "
        "soit favoriser la croissance latérale pour capter autant que possible la faible lumière. "
        "Ce dernier cas peut être observé chez les espèces de sous-bois comme le Hêtre et le Noisetier.",

    "favor_bright": "Lumineux",
    "favor_bright_tt":
        "Imaginez les rameaux d'un arbre comme des milliers de plantes individuelles. "
        "Les plus lumineux poussent vigoureusement, les ombragés meurent - c'est Favor Bright à son maximum. "
        "Maintenant, reliez les plantes avec des branches - pour leur donner un moyen de partager leurs gains. "
        "Lorsque le sucre circule librement et que la lumière est abondante, "
        "même les plantes ombragées recevront le soutien dont elles ont besoin pour grandir et trouver une nouvelle lumière.",

    # Drop
    "auto_prune_enabled": "Élagage automatique",
    "auto_prune_enabled_tt":
        "L'élagage automatique est une taille annuelle des branches latérales pour dégager la base de l'arbre. "
        "Cela permet d'avoir une vue dégagée et de faciliter le passage des piétons et de la circulation. "
        "Supprimez les branches basses endommagées par le gel au sol. Et perdez des branches à cause des animaux qui se nourrissent. "
        "Cette taille est effectuée automatiquement chaque année.",

    "auto_prune_dangling": "Pendantes",
    "auto_prune_dangling_tt":
        "Les branches juste au-dessus de la hauteur d'élagage automatique continuent de pousser sur les côtés et se courbent vers le bas avec la masse accrue. "
        "Ces branches pendantes peuvent être laissées à pousser comme dans un saule pleureur, ou vous pouvez les tailler jusqu'à une certaine hauteur.",

    "auto_prune_low": "Bas",
    "auto_prune_low_tt":
        "L'élagage automatique est une taille annuelle des branches latérales basses pour dégager la base de l'arbre. Cet élagage se met en place progressivement à mesure que l'arbre grandit, "
        "et pour maintenir l'arbre en bonne santé, il ne taille jamais plus d'un tiers de la hauteur de l'arbre.",

    "auto_prune_keep_thick": "Garder épaisses",
    "auto_prune_keep_thick_tt":
        "Ne taillez que les branches plus fines et conservez les plus épaisses. "
        "Cela permettra à l'arbre de faire pousser plusieurs grosses branches principales, donnant à votre arbre un aspect plus naturel - "
        "un aspect que les paysagistes recherchent lors de la taille d'arbres disposant de plus d'espace, comme dans un parc. "
        "Cela se produit également dans la nature, où les animaux qui se nourrissent préfèrent les branches fraîches et juteuses et laissent les branches épaisses tranquilles.",

    "drop_shaded": "Ombragées",
    "drop_shaded_tt":
        "Chute des branches ombragées. "
        "Chaque année, un arbre fera pousser d'innombrables nouveaux rameaux dans toutes les directions. "
        "Ces branches sensibles explorent de nouveaux espaces et cherchent la lumière. "
        "L'arbre investira ensuite son énergie uniquement dans les rameaux bien éclairés et laissera tomber les nombreux ombragés. "
        "Diminuez pour conserver davantage de branches et faire pousser un arbre plus dense. "
        "Augmentez vers 1 pour laisser tomber des branches de plus en plus lumineuses et faire pousser un arbre transparent et ouvert.",

    "drop_decay": "Rester",
    "drop_decay_tt":
        "Gardez les branches mortes sur l'arbre, laissez-les se désagréger lentement. "
        "Il faut un certain temps pour que les branches mortes se dessèchent ou pourrissent et se détachent de l'arbre. Surtout le tronc inférieur "
        "d'un arbre conifère est plein de branches mortes.",

    "drop_weak": "Faibles",
    "drop_weak_tt":
        "La vigueur de croissance d'une branche est déterminée dans le panneau Favor. "
        "Les branches très vigoureuses sont là pour faire grandir l'arbre à de nouvelles hauteurs. "
        "Les branches faibles cessent de croître en longueur - certaines sont rejetées tandis que d'autres sont réaffectées pour former des fleurs et des fruits. "
        "Les branches latérales peuvent toujours prendre le relais.",

    # Add
    "add_side_branches": "Bourgeons",
    "add_side_branches_tt":
        "Le nombre de bourgeons par nœud influence directement l'arrangement géométrique des branches, avec des motifs "
        "alternés, opposés et verticillés correspondant respectivement à un, deux et trois à six bourgeons. "
        "La vigueur de croissance associée à la chance détermine combien de ces bourgeons se développeront effectivement en nouvelles branches.",

    "add_chance": "Chance",
    "add_chance_tt":
        "Probabilité qu'un jeune nœud crée une nouvelle branche. "
        "Tous les bourgeons ne s'ouvriront pas et ne feront pas pousser une nouvelle branche. "
        "Certains sont endommagés par le gel ou les insectes, d'autres sont supprimés par Favor End.",

    "add_bud_life": "Durée de vie du bourgeon",
    "add_bud_life_tt":
        "Chez la plupart des espèces, les bourgeons ne survivent que quelques années. "
        "Les bourgeons âgés jusqu'à cet âge sont viables pour faire pousser une nouvelle rameau. "
        "Sur d'autres, presque tous les bourgeons s'ouvrent et forment principalement une très courte rameau limitée par la dominance apicale. "
        "La plupart d'entre eux disparaîtront bientôt, tandis que quelques-uns échapperont à la répression et se transformeront en nouvelles branches.",

    "add_only_on_end": "Seulement à l'extrémité",
    "add_only_on_end_tt":
        "Ajouter uniquement de nouvelles branches aux nœuds d'extrémité. "
        "Les arbres comme les conifères suppriment la croissance latérale avec des hormones. "
        "En pratique, cela signifie que seuls les nœuds très proches de la pointe sont exempts d'hormones et peuvent "
        "former de nouvelles branches.",

    "add_fork": "Fourche",
    "add_fork_tt":
        "Lorsqu'une branche est particulièrement solide et pousse vigoureusement, elle peut développer plusieurs bourgeons près "
        "de la pointe qui peuvent surpasser le bourgeon terminal. La branche se divise alors en plusieurs branches tout aussi vigoureuses. "
        "Sans branche dominante au milieu pour les pousser sur les côtés, les branches bifurquées poussent à la moitié "
        "de l'angle habituel. Au lieu de former un tronc unique et bien défini, un arbre bifurqué crée une structure évasée "
        "de branches principales.",

    "add_regenerate": "Régénérer",
    "add_regenerate_tt":
        "Ajoutez des pousses régénératrices pour réparer la cime d'un arbre fortement endommagé ou taillé. "
        "Elles apparaissent là où, et quand, il y a un surplus d'énergie dans les racines et les branches, et relativement peu de feuillage. "
        "Tous les arbres ne peuvent pas faire pousser des pousses régénératrices, comme la plupart des conifères. De ce fait, ces espèces ne réagissent pas bien à la taille.",

    "add_planar": "Plan",
    "add_planar_tt": "Similaire à tourner à l'horizontal, mais maintenant de nouvelles branches poussent de manière planaire par rapport à la direction de croissance.",

    "add_horizontal": "Horizontal",
    "add_horizontal_tt":
        "Plagiotropisme pour les bourgeons. "
        "Rotation de l'angle de phyllotaxie vers une orientation horizontale.",

    "add_angle": "Angle",
    "add_angle_tt":
        "L'angle entre la branche existante et une nouvelle branche latérale ajoutée. "
        "Les angles entre 0 et 90 degrés vont d'une continuation droite de la branche existante, "
        "à une direction perpendiculaire.",

    "add_twist": "Torsion",
    "add_twist_tt":
        "Torsion de chaque nœud successif. "
        "Des espèces comme le marronnier d'Inde ont une torsion très visible le long de la longueur de leurs branches, "
        "on peut clairement voir le motif de l'écorce tourbillonnant autour du tronc. "
        "Outre la qualité visuelle évidente, la torsion ajoute également à la rotation phyllotaxique des bourgeons. "
        "Cela améliore la répartition des branches sur les arbres à ramification opposée.",

    # Grow
    "grow_length": "Longueur",
    "grow_length_tt":
        "Une branche vigoureuse pousse de cette longueur à chaque développement. "
        "Les branches plus faibles poussent moins longtemps.",

    "grow_nodes": "Nœuds",
    "grow_nodes_tt":
        "Le nombre maximal de nœuds qu'une branche peut développer chaque année. "
        "Les branches moins vigoureuses développeront moins de nœuds.",

    "shade_elongation": "Plus long à l'ombre",
    "shade_elongation_tt":
        "Les branches ombragées poussent plus longtemps ou plus courtes. "
        "Les plantes poussant à l'ombre s'allongent dans l'espoir de trouver de la lumière. "
        "Associé à une diminution de l'épaisseur, cela crée des branches plus longues mais plus faibles qui se courbent davantage. "
        "Cela peut initier les branches pendantes souvent observées au bas de la couronne.",

    # Turn
    "turn_up": "Vers le haut",
    "turn_up_tt":
        "Gravitropisme négatif. Tourner la nouvelle croissance vers le haut et à l'écart de la gravité. "
        "Utilisez des valeurs négatives pour pousser vers le bas à la place.",

    "turn_up_in_shade": "Vers le haut à l'ombre",
    "turn_up_in_shade_tt": "Tourner la croissance ombragée vers le haut et à l'écart de la gravité. Utilisez des valeurs négatives pour pousser vers le bas à la place.",

    "turn_to_light": "Vers la lumière",
    "turn_to_light_tt":
        "Phototropisme. "
        "Orienter la nouvelle croissance vers la direction la plus lumineuse. "
        "C'est cet effet qui fait pousser une plante d'intérieur vers une fenêtre. "
        "Pour un arbre, cet effet améliorera sa répartition des branches.",

    "turn_to_horizon": "Vers l'horizon",
    "turn_to_horizon_tt":
        "Plagiotropisme. "
        "Orienter la croissance des branches vers le plan horizontal lorsqu'une branche est ombragée.",

    "turn_random": "Aléatoire",
    "turn_random_tt":
        "La branche est libre de se déplacer dans des directions aléatoires et incontrôlées - sans être guidée par la lumière ou la gravité.",

    # Interact
    "react_block_object": "Bloquer",
    "react_block_object_tt":
        "Arrêtez de pousser après avoir heurté cet objet.",

    "react_shade_object": "Ombrage",
    "react_shade_object_tt":
        "Cet objet bloque la lumière, comme dans le cas d'un bâtiment ou peut-être d'une formation rocheuse. "
        "Observez comment vos arbres réagissent à des conditions difficiles et comment ils se dirigent vers la lumière.",

    "react_deflect_object": "Dévier",
    "react_deflect_object_tt": "Éviter cet objet.",

    "react_attract_object": "Attirer",
    "react_attract_object_tt":
        "Pousser vers cet objet. "
        "Les branches peuvent pousser librement à travers cet objet.",

    "react_vigor_object": "Vigueur",
    "react_vigor_object_tt":
        "Sélectionnez un objet qui contrôle la vigueur de la nouvelle croissance.",

    "react_force": "Force",
    "react_force_tt":
        "La magnitude de la force que l'objet exerce sur l'arbre.",

    "react_falloff": "Atténuation",
    "react_falloff_tt":
        "L'effet est plus fort près de l'objet, et diminue de manière exponentielle avec la distance de l'objet.",

    # Épaissir
    "thicken_tips": "Pointes",
    "thicken_tips_tt":
        "Diamètre aux extrémités des branches. "
        "Ceci est l'épaisseur de la pointe lorsqu'une branche a une vigueur maximale. "
        "Une branche moins vigoureuse peut avoir une épaisseur réduite.",

    "thicken_tips_reduce": "Réduire",
    "thicken_tips_reduce_tt":
        "Réduire l'épaisseur des pointes en croissance sur les branches moins vigoureuses. "
        "Une croissance plus fine est plus flexible, ce qui affecte grandement la forme de l'arbre. "
        "Cela est particulièrement important pour les conifères tombants, qui ont tendance à supprimer la vigueur des branches latérales.",

    "thicken_join": "Accroître",  # Fusion, Jonction, Combinaison.
    "thicken_join_tt":
        "L'épaisseur commence à la pointe de la branche et à chaque jonction de deux branches ou plus, "
        "leurs sections transversales se rejoignent pour créer une branche plus forte et plus épaisse. "
        "Ce processus se poursuit jusqu'à la base de l'arbre. "
        "Faire varier le taux de croissance en épaisseur changera considérablement la forme de l'arbre. "
        "L'épaisseur ajoutée renforcera les branches et réduira la flexion.",

    "thicken_base_scale": "Échelle",
    "thicken_base_scale_tt":
        "Augmenter l'épaisseur à la base. "
        "À la racine du tronc, augmenter l'épaisseur causée par la croissance des racines.",

    "thicken_base_shape": "Forme",
    "thicken_base_shape_tt":
        "Ajuster la forme de l'échelle des racines en fusionnant dans le tronc.",

    "thicken_base_buttress": "Contrefort",
    "thicken_base_buttress_tt":
        "Multiplier l'échelle de base avec les saillies de racines. "
        "Les racines en contrefort sont des saillies le long de la base, principalement trouvées dans les arbres tropicaux.",

    "root_distribution": "Distribution",
    "root_distribution_tt":
        "Portée de l'effet de l'échelle des racines sur le tronc.",


    # Bend
    "bend_mass": "Masse",
    "bend_mass_tt":
        "Quantité de flexion sous le poids des branches. "
        "La flexion des branches a un impact significatif sur la forme des arbres, surtout lorsqu'ils vieillissent. "
        "La quantité de flexion de chaque branche dépendra de son épaisseur - les branches plus épaisses pèsent plus, "
        "mais leurs sections transversales accrues les rendent exponentiellement plus résistantes dans leur lutte contre la gravité.",

    "bend_twig_mass": "Masse de rameau",
    "bend_twig_mass_tt":
        "La masse attachée aux extrémités des branches, qui comprend le bois d'une rameau, ses feuilles et ses fruits. "
        "Les arbres essaient de contrer cette flexion en poussant vers le haut avec un gravitropisme négatif (Tourner > Haut). "
        "Cette interaction entre la flexion et le gravitropisme joue un rôle important dans la formation de "
        "soit un caractère d'arbre fastigié ou pleureur.",


    # Shade
    "shade_area": "Surface foliaire",
    "shade_area_tt":
        "Zone de projection d'ombre à l'extrémité de chaque branche, en dm². "
        "Une surface foliaire de 4.0 équivaut à quatre fois une surface de 10 cm x 10 cm. "
        "Notez que cela représente la surface foliaire combinée de la rameau, et non la surface d'une seule feuille.",


    "shade_area_reduce": "Réduire",
    "shade_area_reduce_tt":
        "Diminuez la surface foliaire sur les branches moins vigoureuses.",

    "shade_sensitivity": "Sensibilité",
    "shade_sensitivity_tt":
        "Sensibilité à l'ombre. "
        "L'ombre est une valeur linéaire de clair à foncé, mais les processus dans la nature réagissent souvent de manière exponentielle. "
        "Réglez sur 0 pour une réponse lente à l'ombre, une branche ne réagira qu'après avoir reçu une quantité importante d'ombre. "
        "Réglez sur 1 pour une réaction immédiate, la moindre ombre est amplifiée de manière disproportionnée.",

    "shade_leaf_sides": "Côtés",
    "shade_leaf_sides_tt":
        "Distribuez également les zones de feuilles ombragées le long des côtés des branches. "
        "La plupart des arbres peuvent être simulés avec juste les feuilles aux extrémités des branches, "
        "une petite abstraction qui fonctionne bien. Mais sur les arbres avec des branches pleureuses, "
        "des ramilles latérales sont nécessaires. Notez que vous avez besoin d'une plus petite zone de feuilles avec cela, "
        "parce que plus de ramilles seront placées.",

    "tweak": "Ajuster",
    "tweak_tt": "Ajuste ces paramètres dans la vue, avec une visualisation en 3D des changements.",

    "shade_area_depth": "Profondeur",
    "shade_area_depth_tt":
        "Augmentez les côtés des ombres pour donner plus de profondeur à la forme. "
        "Cela provoquera plus d'ombre sur les côtés de l'arbre et plus d'ombre en général. "
        "Vous pouvez compenser en réduisant les ombres projetées. "
        "Activez l'aperçu des ombres pour voir l'effet.",


    # Build
    "build_resolution": "Résolution",
    "build_resolution_tt":
        "Le nombre de sommets à la base de l'arbre, où il est le plus épais.",

    "build_resolution_reduce": "Réduire",
    "build_resolution_reduce_tt":
        "Réduire les polygones sur les branches plus fines. "
        "La plupart des polygones d'un arbre se trouvent dans ses milliers de jeunes branches. "
        "Ces branches fines peuvent se contenter de moins de polygones sans perdre en qualité visuelle.",

    "smooth": "Lissage",
    "smooth_tt":
        "Réduire l'angle des coins aigus pour créer des branches qui se courbent plus doucement.",

    "texture_bark": "Écorce",
    "texture_bark_tt": "Choisissez une texture",

    "texture_repeat": "Répétition",
    "texture_repeat_tt":
        "Nombre de fois à répéter la texture d'écorce autour de la circonférence de la base de l'arbre - "
        "automatiquement réduit sur les branches plus fines.",

    "texture": "Texture",

    "simulation_scale":
        "Échelle",
    "simulation_scale_tt":
        "Adapter un préréglage à une taille de rameau différente. "
        "Une rameau moyenne contient une ou deux années de croissance et mesure environ 30 cm de long. "
        "Un préréglage est conçu pour correspondre à cette taille. Mais les modèles de rameaux peuvent être de n'importe quelle taille, "
        "d'une seule feuille à plusieurs années de croissance. "
        "La façon d'adapter une rameau de taille différente est de simplement agrandir ou réduire le modèle d'arbre. "
        "Cela permet de conserver vos rameaux à la même échelle grandeur nature.",

    "twig_menu": "Rameaux",
    "twig_menu_tt":
        "Choisissez un ensemble de rameaux à ajouter à votre arbre. "
        "Ce menu liste toutes les rameaux qu'il peut trouver dans le dossier des rameaux - "
        "vous pouvez sélectionner un dossier dans les préférences utilisateur de Grove. "
        "Ou vous pouvez également choisir des objets de la scène actuelle.",

    "twig_pick_objects": "Objets de la scène",
    "twig_pick_objects_tt": "Choisissez n'importe quel objet 3D de la scène.",

    "twig_no_twigs": "Pas de rameaux",
    "twig_no_twigs_tt": "Pas de rameaux",

    "twig_object_end": "Extrémité",
    "twig_object_end_tt":
        "Objet rameau à répartir aux extrémités des branches. "
        "Les rameaux d'extrémité sont de nouvelles pousses avec des feuilles et parfois des fleurs et plus tard des fruits. "
        "Les rameaux d'extrémité sont des extensions des branches existantes - souvent beaucoup plus solides et plus longues que les rameaux latérales.",

    "twig_object_side": "Côté",
    "twig_object_side_tt":
        "Objet rameau à répartir le long des côtés des branches. "
        "Les rameaux latérales sont de nouvelles branches fraîches qui se développent le long des côtés des branches existantes. "
        "Elles portent des feuilles, et parfois des fleurs et plus tard des fruits. "
        "Les rameaux latérales sont souvent plus courtes que les rameaux d'extrémité, en raison de la suppression hormonale de la branche principale qui les a créées. "
        "Seules les plus fortes finiront par se développer en nouvelles branches complètes.",

    "twig_density": "Densité",
    "twig_density_tt":
        "Contrôlez la densité du feuillage de votre arbre en ajoutant plus ou moins de rameaux latérales. "
        "Cela affecte également la densité des rameaux mortes. "
        "Les rameaux d'extrémité ne sont pas affectées et sont toujours ajoutées à chaque extrémité de branche vivante.",

    "twig_view_detail": "Détail de la vue",
    "twig_view_detail_tt":
        "Réduisez la résolution d'affichage des rameaux. "
        "Pour une meilleure performance de la fenêtre d'affichage, cela ajoute un modificateur Decimate à chaque modèle de rameau. "
        "Les fenêtres d'affichage utilisent le modèle modifié, à basse résolution - tandis que les moteurs de rendu utilisent l'original.",

    "use_adaptive_units": "Utiliser des unités adaptatives",
    "use_adaptive_units_tt":
        "Grove utilise des unités pour plusieurs de ses paramètres, dont certains représentent de petites distances. "
        "Avec les unités adaptatives activées, 0,001 m s'affiche comme 1 mm.",

    "language": "Langue",
    "language_tt": "Langue à utiliser pour l'interface et les infobulles",

    "favor_rising": "Verticales",
    "favor_rising_tt":
        "Privilégiez les branches qui poussent vers le haut plutôt que celles qui pendent vers le bas. "
        "Boostez les branches vers le haut pour obtenir un arbre imposant. "
        "Une valeur de 1 ira jusqu'à réduire la vigueur des branches horizontales à zéro.",

    "grove": "Bosquet",

    "label_direction": "Direction de départ",
    "panel_auto_prune": "Élagage automatique",

    "label_layers": "Attributs",

    "branching_inefficiency": "Inefficacité",
    "branching_inefficiency_tt":
        "Une manière directe de limiter la vigueur des branches latérales et de leurs branches latérales consécutives. "
        "Une fixation de branche est imparfaite et limite le transport de l'eau.",

    "sapwood": "Aubier",
    "sapwood_tt":
        "Épaisseur du bois vivant. Il s'agit du bois vivant qui transporte l'eau. Le cœur de la branche à l'intérieur est "
        "du bois mort et sert uniquement de structure de soutien, appelé duramen. Augmenter "
        "cette valeur entraînera une accumulation d'épaisseur moindre sur les branches plus épaisses.",

    "twig_side_on_tips": "Latéral sur les extrémités",
    "twig_side_on_tips_tt":
        "En plus des extrémités, ajoutez également des rameaux latéraux à l'extrémité de chaque branche. "
        "Reconstruisez votre arbre pour voir l'effet.",

    "rebuild": "Reconstruire",
    "rebuild_tt":
        "Reconstruire les maillages de vos modèles d'arbres. "
        "Reconstruisez vos arbres pour mettre à jour la réduction des polygones, les couches de sommets et la distribution des rameaux latéraux.",

    "add_new_grove": "Ajouter un bosquet",
    "add_new_grove_tt": "Ajouter une nouvelle collection de bosquets.",

    "select_a_grove_collection": "Choisir collection Grove.",

    "select_linked_branches_tt": "Étendre la sélection actuelle à l'ensemble de la branche et de ses branches latérales.",
    "select_linked_branches": "Sélectionner les branches liées",

    "select_thicker": "Sélectionner plus épais",
    "select_thicker_tt": "Sélectionner la géométrie appartenant aux nœuds de branches plus épais, en utilisant l'attribut Épaisseur.",
    "select_thicker_threshold": "Seuil",

    "show_dead_preview": "Montrer les morts",

    "twig_pick_collections": "Collections",
    "twig_pick_collections_tt": "Sélectionnez n'importe quelle collection d'objets de rameaux dans le fichier actuel.",

    "disable_outline": "Désactiver le contour",
    "disable_outline_tt":
        "Cliquez pour désactiver le rendu des contours pour une représentation correcte de l'arbre et un meilleur "
        "retour visuel lors des ajustements. Le rendu des contours fait apparaître les branches beaucoup plus épaisses qu'elles ne le sont réellement.",

    "set_background": "Éclaircir l'arrière-plan",
    "set_background_tt":
        "Cliquez pour éclaircir l'arrière-plan de votre fenêtre d'affichage et le régler sur un gris moyen. "
        "Les branches des arbres seront beaucoup plus faciles à voir et vos arbres auront un meilleur aspect.",

    "bend_twig_mass_solidify": "Solidifier",
    "bend_twig_mass_solidify_tt":
        "Solidifiez la courbure causée par le poids tirant vers le bas sur les extrémités des branches. "
        "La masse des rameaux varie avec les saisons, les lourdes fleurs de printemps, "
        "les grandes feuilles et les fruits volumineux tirent tous la branche vers le bas. "
        "Mais lorsque vient le moment où la branche devient rigide, la plupart de cette masse peut déjà être tombée. ",

    "add_up": "Haut",
    "add_up_tt":
        "Une nouvelle branche latérale commence dans une direction ascendante. Utilisez des valeurs négatives pour pousser vers le bas à la place.",

    # Record
    "record_enabled": "Enregistre",
    "record_enabled_tt":
        "Enregistrez la croissance sous forme de séquence d'objets dans une collection dédiée appelée \"Record\". "
        "Chaque étape est clé en main pour la visibilité pendant une courte période. "
        "Tous ces objets en séquence forment votre animation de croissance.",

    "record_start": "Frame de début",
    "record_start_tt":
        "Décalez l'animation dans le temps pour qu'elle commence à cette frame.",

    "record_interval": "Intervalle",
    "record_interval_tt":
        "Chaque année est une interpolation fluide, de la forme initiale de l'arbre au printemps, à sa forme adulte en été. "
        "Définissez le nombre de frames pour cette interpolation - et ainsi la vitesse de croissance. "
        "Vous pouvez ajuster cette valeur à tout moment, votre animation sera mise à jour instantanément.",

    "regrow": "Repousser",
    "regrow_tt":
        "Redémarrez et faites rapidement repousser les arbres jusqu'à l'âge actuel - en sautant les étapes de construction, "
        "mais aussi en sautant les occasions de tailler votre arbre.",

    "twig_hide": "",
    "twig_hide_tt": "Masquez les rameaux dans la fenêtre d'affichage pour une vue dégagée des branches ou un affichage plus rapide.",

    "twig_longevity": "Longévité",
    "twig_longevity_tt":
        "Les rameaux latéraux apparaissent près de l'extrémité de chaque branche, sur les nouveaux nœuds poussés cette année. "
        "La longévité permet aux rameaux de durer des années supplémentaires, en les maintenant sur des nœuds de plus en plus anciens. "
        "Cela nécessite une reconstruction pour montrer les changements.",

    "replant_grove": "Replanter",
    "replant_grove_tt": "Replanter.",

    "manual_bend": "Courber",
    "manual_bend_tt":
        "Un outil inspiré de la technique du bonsaï qui consiste à courber les branches avec du fil métallique. Mais beaucoup plus flexible, "
        "capable de courber même les branches les plus épaisses et de styliser même un arbre adulte.",

    "twig_object_upward": "Vertical",
    "twig_object_upward_tt":
        "Modèle de rameau qui pousse fortement vers le haut. "
        "Les rameaux qui poussent vers le haut sont souvent encore plus longs et ont leurs feuilles tournées dans toutes les directions. "
        "Ce rameau est facultatif; s'il n'est pas sélectionné, il utilisera le rameau d'extrémité à la place.",

    "twig_object_dead": "Mort",
    "twig_object_dead_tt":
        "Modèle d'un rameau faible ou mort. "
        "Ce rameau est facultatif et peut être utilisé pour ajouter des détails aux parties les plus faibles d'un arbre.",

    "import_preset": "Importer un fichier de graine...",
    "import_preset_tt":
        "Un preset est stocké dans un fichier .seed.json que vous pouvez partager avec d'autres - "
        "importezen un pour l'ajouter à votre liste de presets.",

    "placeholder_delay": "Délai",
    "placeholder_delay_tt":
        "Années à attendre avant de commencer à pousser.",

    "panel_build_base": "Base",

    "twig_wither": "Flétrir",
    "twig_wither_tt":
        "Nombre d'années (après la durée de vie) pendant lesquelles les rameaux morts restent accrochés et se flétrissent sur l'arbre. "
        "Reconstruire pour voir l'effet.",

    "add_tree": "Ajouter un arbre",
    "add_tree_tt":
        "Ajouter un objet vide à partir duquel faire pousser. "
        "Déplacez, tournez, dupliquez ou supprimez cet objet pour faire pousser des groupes d'arbres, chacun à son propre emplacement et angle.",

    "save_preferences": "Enregistrer les préférences",
    "save_preferences_tt": "Enregistrez vos préférences pour mémoriser ce paramètre.",

    "old_release_warning_line_1": "Arbres cultivés dans une ancienne version.",
    "old_release_warning_line_2": "Beaucoup de choses ont changé.",
    "old_release_warning_line_3": "Utilisez l'ancienne version pour modifier.",

    "thicken_deadwood": "Bois mort",
    "thicken_deadwood_tt":
        "Lorsque les branches sont coupées ou élaguées, l'arbre cicatrise partiellement la plaie, "
        "mais une petite partie du noyau meurt. L'arbre compensera cela "
        "en ajoutant plus d'épaisseur à la nouvelle croissance. Ce processus, au fil du temps, "
        "résultera en un tronc plus épais.",

    "grow_together": "Grandir ensemble",
    "grow_together_tt_short":
        "Faites pousser toutes les collections de bosquets ensemble comme un seul.\n"
        "Mélangez les espèces et laissez-les rivaliser pour la lumière.",
    "grow_together_tt":
        "Faites pousser toutes les collections de bosquets séparées ensemble comme un seul, de sorte que vous pouvez mélanger différentes espèces d'arbres."
        "Avec des calculs combinés d'ombre et de phototropisme pour les faire rivaliser pour la lumière.",

    "draw": "Dessiner",
    "draw_tt": "Faites pousser une nouvelle branche le long dun chemin.",

    "prune_status_draw_lines": "Dessiner",

    "bend_status_select_node": "Sélectionner un nœud",

    "bend_tool_distance": "Distance",
    "bend_tool_distance_tt": "Longueur",

    "bend_tool_bend_button": "Plier",
    "bend_tool_bend_button_tt": "Espace",

    "close_button": "",
    "close_button_tt": "Fermer",

    "close": "Fermer",

    "turntable": "",
    "turntable_tt": "Vue",

    "bend_tool_curve": "Courbe",
    "bend_tool_curve_tt": "Forme de la courbure",
    "bend_tool_curve_simple": "Simple",
    "bend_tool_curve_flexible": "Flexible",
    "bend_tool_curve_s_curve": "Courbe en S",


    # Wind
        "wind_vector": "Vent",
    "wind_vector_tt": "Vitesse et direction",
    "wind_turbulence": "Turbulence",
    "wind_turbulence_tt": "Soulevez les ramilles et faites danser les branches dans le vent.",

    "wind_shapes": "Clés de forme",
    "wind_shapes_tt":
        "Chaque forme est clé à 2 images d'intervalle et s'interpole de manière fluide. "
        "Le vent boucle automatiquement",

    "label_animating_wind": "Animation du vent...",
    "label_stop": "Arrêter",

    "wind_breeze": "Brise",
    "wind_breeze_tt":
        "Animez les ramilles avec une animation de brise vivante. "
        "Vous pouvez la combiner avec une animation de vent régulière pour une déformation plus importante.",

    "calculate_wind": "Animer",
    "calculate_wind_tt":
        "Ajoutez une animation de vent. "
        "Cela crée une série de clés de forme qui déforment les branches de votre arbre au fil du temps.",

    "wind_frequency": "Fréquence du vent",
    "wind_frequency_tt":
        "Fréquence du vent.",

    "bend_reaction": "Réaction",
    "bend_reaction_tt":
        "Le bois de réaction permet aux branches qui s'épaississent rapidement de se courber activement vers le haut avec le temps. "
        "L'effet s'intensifie à mesure que la branche s'éloigne davantage d'une direction de croissance verticale. "
        "Les arbres inclinés peuvent revenir à la verticale, et les branches latérales vigoureuses peuvent prendre le relais en tant que branche principale.",


    "grow_tool_growing": "Croissance",
    "grow_tool_growing_tt": "Échapper pour annuler.",
    "grow_tool_building": "Construction du maillage",

    "drop_obsolete": "Obsolète",
    "drop_obsolete_tt":
        "Au fur et à mesure que l'arbre grandit, les branches inférieures sont ombragées et les petites branches tombent. "
        "Les anciennes branches principales seront plus épaisses que nécessaire pour soutenir leur feuillage décroissant. "
        "Incapable de soutenir ce bois excédentaire, la branche finira par devenir obsolète, pourrir et tomber. "
        "Cela se produit également après une taille importante.",

    # Opérateur de plantation.
    "plant_layout": "Disposition",
    "plant_layout_tt": "Plantez un verger, une plantation, une haie, un anneau ou des touffes naturelles d'arbres",

    "plant_trees": "Arbres",
    "plant_trees_tt": "Nombre d'arbres",

    "plant_space": "Espace",
    "plant_space_tt": "Distance entre les arbres",

    "plant_random_shift": "Décalage aléatoire",
    "plant_random_shift_tt": "Placement irrégulier",

    "plant_random_seed": "Graine aléatoire",
    "plant_random_seed_tt": "Varier le décalage aléatoire",

    "plant_delay": "Délai",
    "plant_delay_tt": "Les arbres éloignés du centre commencent à pousser à une année ultérieure.",

    "plant_ring_radius": "Rayon",
    "plant_ring_radius_tt": "Distance du milieu de l'anneau",

    "plant_rows_trees_tt": "Nombre d'arbres par rangée",

    "plant_rows": "Rangées",
    "plant_rows_tt": "Nombre de rangées",

    "plant_rows_space": "Espace",
    "plant_rows_space_tt": "Espace entre les rangées",

    "plant_rows_diagonal": "Diagonale",
    "plant_rows_diagonal_tt": "Décalez chaque seconde rangée pour obtenir un motif en diamant",

    "plant_islands_trees_tt": "Nombre moyen d'arbres par îlot",

    "plant_islands": "Îlots",
    "plant_islands_tt": "Nombre d'îlots d'arbres",

    "plant_islands_space": "Espace des îlots",
    "plant_islands_space_tt": "Distance moyenne entre les îlots d'arbres",

    "plant_islands_clearing": "Clairière",
    "plant_islands_clearing_tt": "Espace ouvert au milieu",

    "plant_islands_randomize": "Aléatoire",
    "plant_islands_randomize_tt": "Variez le nombre d'arbres par îlot",

    "plant_layout_clump": "Touffe",
    "plant_layout_rows": "Rangées",
    "plant_layout_ring": "Anneau",
    "plant_layout_islands": "Îlots",

    "plant_variation_panel": "Variation",
    "plant_diverge": "Diverger",
    "plant_diverge_tt": "S'écarter des arbres voisins.",

    "plant_terrain_panel": "Terrain",
    "plant_terrain_drop": "Abaisser",
    "plant_terrain_drop_tt": "Projeter les arbres au sol.",

    "plant_terrain_slope": "Pente",
    "plant_terrain_slope_tt": "Prendre en compte la pente du paysage dans la rotation.",

    "escape_to_stop": "Échapper pour arrêter",

    "surround_enabled": "Entourer",
    "surround_enabled_tt":
        "Entourez vos arbres d'un mur qui bloque la lumière de tous les côtés. "
        "Les arbres deviennent plus grands et perdent leurs branches inférieures. "
        "Faites pousser un arbre forestier sans avoir à faire pousser toute la forêt.",

    "surround_density": "Densité",
    "surround_density_tt":
        "Cultivez dans un champ ouvert ou une forêt dense, ou tout ce qui se trouve entre les deux.",
    "surround_height": "Hauteur",
    "surround_height_tt":
        "Une hauteur fixe qui peut être utilisée pour les arbres établis ou les bâtiments. "
        "Utilisez la hauteur automatique pour que les environs grandissent avec vos arbres.",
    "surround_grow": "Croître",
    "surround_grow_tt":
        "Augmente automatiquement en hauteur chaque année - les arbres environnants grandissent avec vos arbres.",
    "surround_distance": "Distance",
    "surround_distance_tt": "Espace libre pour grandir.",

    "widget_scale": "Échelle du widget",
    "widget_scale_tt":
        "Ajustez la taille des widgets de l'interface utilisateur radiale s'ils apparaissent trop petits ou grands sur votre écran.",

    'file': "Fichier",
    "file_tt": "Mettez de côté des arbres pour une utilisation ultérieure, ou transférez des arbres entre différentes applications.",

    "file_recent": "Récent",

    "file_import": "Importer des arbres",
    "file_import_tt": "Importer une simulation à partir d'un fichier .grove.",

    "file_export": "Exporter des arbres",
    "file_export_tt": "Exporter la simulation actuelle dans un fichier .grove.",

    "react_enabled": "Réagir",
    "react_enabled_tt":
        "Utilisez des objets maillés pour attirer, dévier ou arrêter la nouvelle croissance. "
        "Faites en sorte qu'un bâtiment projette de l'ombre, ou soyez créatif et faites pousser des arbres dans des formes.",

    "add_chance_reduce": "Réduire",
    "add_chance_reduce_tt":
        "Réduisez la probabilité d'ajouter des branches latérales aux branches moins vigoureuses. "
        "Ajouter moins de branches latérales fera que ces branches accumuleront moins d'épaisseur. "
        "Au final, cela fera que les branches inférieures ombragées et fléchiront vers le sol.",

    "roots": "Racines",
    "roots_tt":
        "Générez des racines de surface. "
        "Les racines poussent généralement sous terre, mais peuvent être exposées par l'érosion du sol. "
        "Visuellement attrayantes, les racines de surface ancrent l'arbre au sol.",

    "roots_roots_panel": "Racines",
    "roots_number": "Nombre",
    "roots_number_tt" : "Nombre de racines principales",
    "roots_nodes" : "Nœuds",
    "roots_nodes_tt" : "Nombre de nœuds par racine",
    "roots_length" : "Longueur",
    "roots_length_tt" : "Longueur entre deux nœuds.",
    "roots_climb" : "Grimper",
    "roots_climb_tt" : "Faites monter les racines le long du tronc pour créer un mélange homogène.",
    "roots_turn_down" : "Pousser vers le bas",
    "roots_turn_down_tt" : "",

    "roots_branches_panel": "Racines latérales",
    "roots_branches_panel_tt": "",
    "roots_generations": "Générations",
    "roots_generations_tt": "Ajoutez d'autres générations pour développer le système racinaire en détail.",
    "roots_density": "Densité",
    "roots_density_tt":
        "Probabilité de faire pousser une racine latérale. Pour augmenter davantage la densité, "
        "augmentez le nombre de nœuds et réduisez la longueur entre les nœuds.",
    "roots_add_angle": "Angle",
    "roots_add_angle_tt": "L'angle par rapport à la racine principale.",
    "roots_add_down": "Ajouter vers le bas",
    "roots_add_down_tt": "",

    "roots_variation_panel": "Aléatoire",
    "roots_random_heading": "Direction",
    "roots_random_heading_tt": "Se faufiler sur le sol.",
    "roots_random_pitch": "Inclinaison",
    "roots_random_pitch_tt": "Se tourner vers le haut et vers le bas en grandissant.",
    "roots_random_seed": "Graine",
    "roots_random_seed_tt": "",

    "roots_thickness_panel": "Épaisseur",
    "roots_thickness": "Épaisseur",
    "roots_thickness_tt": "Épaisseur moyenne d'une racine principale.",
    "roots_thickness_reduce": "Réduire",
    "roots_thickness_reduce_tt": "",
    "roots_thickness_random": "Aléatoire",
    "roots_thickness_random_tt": "",

    "roots_terrain_panel": "Terrain",
    "roots_terrain_panel_tt": "",
    "roots_drop": "Laisser tomber",
    "roots_drop_tt": "",

    "favor_end_reduce": "Réduire",
    "favor_end_reduce_tt":
        "Réduisez l'effet de favoriser les extrémités lorsque la branche pousse à un angle par rapport à la verticale.",

    "restart_single_tree": "Arbre unique",
    "restart_single_tree_tt":
        "Supprimez les espaces réservés et plantez un seul arbre à l'origine.",

    "restart_revert": "Recommencer",
    "restart_revert_tt":
        "Réinitialiser tout par défaut, recharger le préréglage actif et redémarrer avec un seul arbre.",

    "operator_turntable": "Vue",
    "operator_turntable_tt":
        "Observez vos arbres à hauteur des yeux - promenez-vous autour et sous la canopée.",

    "restart_all": "Tout redémarrer",
    "restart_all_tt": "Redémarrer chaque collection de bosquets.",

    "stake_enabled": "Tuteur",
    "stake_enabled_tt": "Un tuteur soutient le tronc pour qu'il pousse droit vers le haut.",
    "stake_height": "Hauteur",
    "stake_height_tt": "Soutenez l'arbre jusqu'à cette hauteur pour que le tronc pousse droit vers le haut.",

    "plant": "Planter",
    "plant_tt":
        "Plantez un groupe d'arbres - créez des vergers, des haies ou des îlots naturels d'arbres. "
        "Cet outil crée des objets vides, que vous pouvez librement déplacer, dupliquer ou supprimer.",
    
    "sow_enabled": "Semer",
    "sow_enabled_tt": "Disperser des graines autour d'arbres existants pour simuler un bosquet d'arbres se propageant naturellement.",
    
    "sow_age": "Délai",
    "sow_age_tt": "Les arbres mettent plusieurs années à s'enraciner et à établir un état énergétique positif avant de commencer à produire des graines.",
    
    "sow_chance": "Probabilité",
    "sow_chance_tt":
        "La chance annuelle que chaque arbre crée une descendance réussie."
        "En réalité, certains arbres peuvent créer des milliers de graines, et des centaines de ces graines peuvent germer chaque année."
        "Mais presque aucune ne survit pour devenir un véritable arbre."
        "Pour maintenir la simulation à une vitesse utilisable, gardez la probabilité basse.",
    
    "sow_distance": "Distance",
    "sow_distance_tt": "Les graines sont dispersées dans une certaine distance autour des arbres existants.",
    
    "sow_limit": "Limite",
    "sow_limit_tt": "Le nombre maximum d'arbres. Arrête d'ajouter de nouveaux arbres au-delà de ce nombre pour maintenir la simulation à une vitesse utilisable.",
    
    "presets_path": "Dossier des préréglages",
    "presets_path_tt": "Sélectionnez le dossier où vous stockez vos préréglages. Tous les préréglages de ce dossier apparaîtront dans le sélecteur de préréglages.",
    
    "use_scientific_names": "Utiliser les noms scientifiques",
    "use_scientific_names_tt": "Affiche les espèces de rameaux en utilisant leurs noms scientifiques, lorsque disponibles. Lorsque désactivé, le menu des rameaux affiche le nom commun en anglais.",
    
    "shade_branches_panel": "Branches",
    "shade_leaves_panel": "Feuilles",
    
    "shade_branches": "Branches",
    "shade_branches_tt": "La plupart de l'ombre provient des feuilles, et pour certains arbres, vous pouvez inclure la géométrie des branches dans le calcul de l'ombre.",
    "shade_alongside": "Le long",
    "shade_alongside_tt": "En plus des rameaux nouvellement développés, des arbres comme les pins ont de vieilles aiguilles le long de leurs branches.",
    "shade_alongside_diameter": "Diamètre",
    "shade_alongside_diameter_tt": "Diamètre de la géométrie projetant de l'ombre le long des branches.",
    
    "build_cutoff_thickness": "Seuil d'épaisseur",
    "build_cutoff_thickness_tt": "Ne construit pas les nœuds en dessous de ce diamètre pour réduire drastiquement le nombre de polygones. Compensez avec des rameaux plus grands qui représentent plusieurs années de croissance.",
    
    "build_cutoff_age": "Seuil d'âge",
    "build_cutoff_age_tt": "Ignore la construction des dernières années de croissance pour réduire drastiquement le nombre de polygones. Compensez avec des rameaux plus grands qui représentent plusieurs années de croissance.",
    
    "build_triangulate": "Trianguler",
    "build_triangulate_tt": "Utiliser uniquement des triangles pour construire les branches de l'arbre, pas de quadrilatères.",
    
    "build_blend": "Transitions",
    "build_blend_tt": "Ajoute des nœuds supplémentaires pour créer une transition douce entre les branches. Ceci est visuellement important pour les branches plus épaisses, mais peut être désactivé pour les branches plus fines afin de réduire drastiquement le nombre de polygones.",
    
    "build_end_cap": "Extrémités",
    "build_end_cap_tt": "Fermez les extrémités ouvertes des branches avec une géométrie supplémentaire, ou ignorez cette étape pour les branches plus fines afin de réduire significativement le nombre de polygones. Selon la distance à l'arbre et si l'arbre est en feuilles ou non, les extrémités plus fines peuvent être presque invisibles de toute façon.",
    
    "detail_simplify": "Simplifier",
    "detail_simplify_tt": "Simplifiez les branches en ignorant les nœuds droits avec presque aucun changement de direction. Cela ne donne qu'une modeste réduction du nombre de polygones.",
    
    # Skeleton
    "build_skeleton": "Construire squelette",
    "build_skeleton_tt": "Créer des os, des groupes de poids d'os et du vent.",
    
    "skeleton": "Squelette",
    "skeleton_tt": "Créer une structure osseuse qui vous permet de déformer et d'animer les arbres. Ajoute également des groupes de sommets pour lier les points du maillage à leurs os respectifs. En option, ajoutez une animation de vent aux nouveaux os.",
    
    "skeleton_panel_bones": "Os",
    "skeleton_panel_wind": "Vent",
    
    "skeleton_reduce": "Réduire",
    "skeleton_reduce_tt": "Ignorer les branches latérales fines pour réduire le nombre d'os.",
    
    "skeleton_bias": "Biais",
    "skeleton_bias_tt": "Augmentez pour ajouter plus d'os vers le haut, diminuez pour ajouter plus d'os vers le bas.",
    
    "skeleton_length": "Longueur",
    "skeleton_length_tt": "Créer des os plus longs pour réduire leur nombre.",
    
    "skeleton_connected": "Connecté",
    "skeleton_connected_tt": "Blender peut construire une hiérarchie à partir d'os flottants, tandis que certains autres programmes nécessitent une chaîne d'os connectés. Les connexions nécessitent un nouvel os à chaque point de ramification, ce qui augmente le nombre d'os.",
    
    # Trial
    "fallback_instructions": "Préparez-vous à la croissance",
    "fallback_instructions_tt": "Suivez les instructions sur http://www.thegrove3d.com/info/install/ pour installer le noyau de simulation.",
    
    "trial_end": "Acheter maintenant...",
    "trial_end_tt": "Votre essai a expiré. Si vous aimez The Grove, veuillez acheter une licence pour continuer à faire pousser de magnifiques arbres.",
}