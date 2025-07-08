# coding=utf-8

dictionary = {

    '': '',

    # Panel titles
    'panel_presets': 'Ajustes',
    'panel_twigs': 'Ramita',
    'panel_twigs_more': 'Mas',
    'panel_simulation': 'Simulación',
    'panel_favor': 'Prioriza',
    'panel_drop': 'Suelta',
    'panel_add': 'Añade',
    'panel_grow': 'Crece',
    'panel_turn': 'Gira',
    'panel_react': 'Reacciona',
    'panel_thicken': 'Aumenta grosor',
    'panel_build_base': 'Base',
    'panel_bend': 'Gravedad',
    'panel_shade': 'Sombrea',
    'panel_build': 'Construye',
    'panel_build_wind': 'Viento',
    'panel_build_mesh': 'Nivel de detalle',
    'panel_build_texture': 'Textura',


    # User preferences
    'set_presets_path': 'Carpeta con ajustes...',
    'presets_path': 'Carpeta con ajustes',
    'presets_path_tt':
        'Selecciona la carpeta donde guardas los ajustes. Todos los ajustes de esta carpeta aparecerán en el selector de ajustes.',
        
    'set_twigs_path': 'Carpeta con ramitas...',
    'twigs_path': 'Carpeta con ramitas',
    'twigs_path_tt':
        'Escoge la carpeta donde guardas las ramitas. '
        'Las ramitas se mostrarán en un menú desplegable.',
    'set_textures_path':'Carpeta con texturas...',
    'textures_path': 'Carpeta con texturas',
    'textures_path_tt':
        'Escoge la carpeta donde guardas las texturas de corteza. '
        'Las texturas se mostrarán en un menú desplegable.',

    'use_adaptive_units': 'Unidades adaptativas',
    'use_adaptive_units_tt':
        'The Grove utiliza unidades para varios de sus parámetros, algunos de los cuales representan distancias minúsculas. '
        'Con las unidades adaptativas activadas, 0,001 m se mostrará como 1 mm.',

    'save_preferences': 'Guarda preferencias',
    'save_preferences_tt': 'Guarda tus preferencias para recordar esta configuración.',


    # Interface messages
    'remove_preset_info': 'Elimina información de ajustes {}?',
    'overwrite_preset_info': 'Reemplaza información de ajustes {}?',
    'name_preset_info': 'Dale un nombre.',
    'planted_trees_info': '{} Árboles de {} fueron plantados.',
    'planted_tree_info': 'Un árbol de {} fue plantado.',
    'leaves_structure_info': 'Hojas no son compatibles con Estructura.',
    'tips_info': 'Consejos:',


    # Presets
    'presets_menu': '',
    'presets_menu_tt': 'Leer los parámetros preestablecidos de la especie arbórea',

    'preset_name': 'Nuevo nombre',
    'preset_name_tt': 'Nombre del ajuste a añadir',

    'remove_preset': 'Borra',
    'remove_preset_tt': 'Elimina ajuste seleccionado',

    'cancel_action': 'Cancela',

    'remove_preset_confirm': 'Sí',
    'remove_preset_confirm_tt': 'Confirma borrar el ajuste',

    'rename_preset': 'Renombra',
    'rename_preset_tt': 'Renombra ajuste seleccionado',

    'add_preset': 'Añade',
    'add_preset_tt': 'Agrega nuevos ajustes',

    'overwrite_preset': 'Reemplaza',
    'overwrite_preset_tt': 'Reemplaza ajuste seleccionado',

    'overwrite_preset_confirm': 'Sí',
    'overwrite_preset_confirm_tt': 'Confirma reemplezar el ajuste',

    'save_preset': 'Guarda',
    'save_preset_tt': 'Guarda la configuración actual como nuevos ajustes.',


    # Simulate
    'simulation_scale':
        'Escala',
    'simulation_scale_tt':
        'Adaptar un ajuste a un tamaño de rama diferente. '
        'Una ramita contiene uno o dos años de crecimiento en promedio y tiene unos 30 cm de largo. '
        'Un preset está diseñado para que coincida con este tamaño. '
        'Pero los modelos de ramita pueden ser de cualquier tamaño que desee, '
        'desde una única hoja hasta varios años de crecimiento. '
        'La forma de igualar una ramita de diferente tamaño es simplemente escalar el modelo de ramas arriba o abajo.',

    'simulation_flushes': 'Ciclos',
    'simulation_flushes_tt':
        'Cantidad de años para crecer. '
        'Simula tu árbol en pasos pequeños e interactivos.',

    'zoom': 'Vista',
    'zoom_tt': 'Haz doble clic para andar alrededor de tus árboles.',

    'simulate': 'Crece',
    'simulate_tt':
        'Crece tu árbol en pasos interactivos. '
        'Simula las estaciones mediante el crecimiento, la flexión y la poda en pasos interactivos. '
        'Observa cómo tu árbol evoluciona año tras año.',

    'restart': 'Reinicie',
    'restart_tt':
        'Empeza de nuevo. '
        'Ajustar el carácter de tu árbol es a menudo un proceso de ensayo y error. '
        'E incluso cuando los ajustes son inmejorables, la naturaleza no es perfecta. '
        'Crece, ajustar, reiniciar y repetir...',

    'manual_prune': 'Poda',
    'manual_prune_tt':
        'Dibuja líneas en la vista 3D para eliminar o acortar las ramas no deseadas.',

    # Flow
    'favor_end': 'Puntas',
    'favor_end_tt':
        'Añade ramas laterales más cortas y menos vigorosas para promover un crecimiento más largo desde el extremo de la rama.',

    'favor_end_reduce': 'Reduce',
    'favor_end_reduce_tt':
        'Reduce el efecto cuando la rama crece en ángulo a partir de la vertical.',

    'favor_bright': 'Iluminadas',
    'favor_bright_tt':
        'Imagina las ramitas de un árbol como miles de plantas individuales. '
        'Las más iluminadas crecen vigorosamente, las sombreadas mueren; este es el efecto al máximo de este parámetro. '
        'Luego, conecta las plantas con ramas para darles una manera de compartir sus ganancias. '
        'Cuando el azúcar fluye libremente y la luz es abundante, incluso las plantas sombreadas recibirán el apoyo que necesitan para crecer y encontrar nueva luz.',

    'favor_rising': 'Verticales',
    'favor_rising_tt':
        'Favorezca ramas que crecen hacia arriba en lugar de ramas que cuelgan hacia abajo. '
        'Dar un impulso a ramas ascendentes para obtener un árbol en altura. '
        'Un valor de 1 llegará a reducir el vigor de ramas horizontales a cero. ',


    # Auto prune
    'auto_prune_enabled': 'Poda automática',
    'auto_prune_enabled_tt':
        'Pode la base de los árboles de la ciudad para permitir el paso de los peatones y del tráfico. '
        'Tire las ramas bajas dañadas por las heladas del suelo. '
        'Y pierda las ramas por los animales que buscan comida. '
        'Esta poda se realiza automáticamente cada año.',

    'auto_prune_low': 'Bajas',
    'auto_prune_low_tt':
        'Suelta ramas bajas y corta ramas que cuelgan bajo. '
        'Poda automáticamente la base de los árboles en la ciudad para permitir el paso libre para los peatones y el tráfico. '
        'Corta las ramas colgantes bajas dañadas por helada o para dar de forraje a animales. '
        'Esta poda comienza gradualmente cuando un árbol crece más alto.',

    'auto_prune_keep_thick': 'Mantene gruesas',
    'auto_prune_keep_thick_tt':
        'Mantén las ramas bajas suficientemente gruesas para ser comidas por los animales. '
        'Los animales prefieren las ramas frescas y dejan las gruesas crecer. '
        'Esto permitirá que el árbol desarrolle varias ramas principales grandes, dando a tu árbol un aspecto más natural. '
        'Un aspecto que los jardineros también buscan al podar árboles que tienen más espacio en jardines y parques.',

    'auto_prune_dangling': 'Colgantes',
    'auto_prune_dangling_tt':
        'Las ramas justo por encima de la altura de la autopoda continúan creciendo hacia los lados y se doblan hacia abajo con el aumento de su masa. '
        'Estas ramas colgantes pueden dejarse crecer como en un sauce llorón o podarse a una altura establecida.',

    # Drop
    'drop_shaded': 'Sombreadas',
    'drop_shaded_tt':
        'Solta ramas sombreadas. '
        'Disminuye para mantener más ramas y crecer un árbol más denso. '
        'Aumenta hacia 1 para dejar caer ramas cada vez más brillantes, '
        'creciendo un árbol transparente y abierto.',

    'drop_obsolete': 'Obsoletas',
    'drop_obsolete_tt':
        'Mientras el árbol sigue creciendo, las ramas inferiores se sombrean y las pequeñas caen. '
        'Las viejas ramas principales serán más gruesas de lo necesario para sostener su follaje en disminución. '
        'Incapaz de sostener este exceso de madera, la rama eventualmente se volverá obsoleta, se pudrirá y caerá. '
        'Esto también sucede después de la poda pesada.',

    'drop_decay': 'Mantene muertas',
    'drop_decay_tt':
        'Mantén las ramas muertas en el árbol. '
        'Lleva tiempo para que ramas muertas se pudran y desprendan del árbol. '
        'Especialmente el tronco inferior de las coníferas está poblado de ramas muertas.',

    'drop_weak': 'Sin éxito',
    'drop_weak_tt': 'Poder por debajo del cual un extremo de rama forma una flor y luego deja de crecer en longitud.',

    # Add
    'add_side_branches': 'Yemas',
    'add_side_branches_tt':
        'El número de yemas por nodo influye directamente en la disposición geométrica de las ramas, con patrones '
        'alternos, opuestos y verticilados correspondientes a una, dos y tres a seis yemas, respectivamente. '
        'El vigor de crecimiento junto con la probabilidad determina cuántas de estas yemas realmente se desarrollarán como nuevas ramas.',
    
    'add_chance': 'Posibilidad',
    'add_chance_tt':
        'Posibilidad de que un nodo joven cree una nueva rama. '
        'No todos las yemas se abrirán y crecerán una nueva rama. '
        'Algunos están dañados por la escarcha o los insectos, otros son suprimidos por Estimular Corrientes.',

    'add_chance_reduce': 'Reducción',
    'add_chance_reduce_tt':
        'Reduzca la posibilidad de añadir nuevas ramas laterales a las ramas menos vigorosas. '
        'Añadir menos ramas laterales reducirá a su vez la acumulación de grosor en estas ramas. '
        'Al final, esto hará que las ramas más bajas en la sombra caigan hacia abajo.',

    'add_horizontal': 'Horizontal',
    'add_horizontal_tt':
        'Girar el ángulo de rotación filotáxica hacia la orientación horizontal.',

    'add_angle': 'Ángulo',
    'add_angle_tt':
        'Ángulo entre una nueva rama y su superior. '
        'Los ángulos entre 0 y 90 grados van desde una continuación recta de la rama, '
        'hasta una dirección perpendicular a la rama superior.',

    'add_twist': 'Retorcer',
    'add_twist_tt':
        'Retorcer cada nodo sucesivo. '
        'Esto se añade a la rotación filotáxica de yemas alrededor de la rama. '
        'Especies como el castaño de Indias tienen torsión muy visible a lo largo del tronco, '
        'lo que también mejora su distribución de ramas. '
        'Como beneficio adicional, la retorsión también ayuda a ocultar la repetición de la textura.',

    'add_bud_life': 'Vida de las yemas',
    'add_bud_life_tt':
        'En la mayoría de las especies, las yemas sólo sobreviven un par de años. '
        'Las yemas hasta esta edad son viables para formar una ramita nueva.'
        'En otras especies, casi todas las yemas se abren y forman ramas muy cortas que están restringidas por la dominancia apical. '
        'La mayor parte de estas pronto desaparecerán, mientras que pocas de ellas se desarrollan y forman nuevas ramas.',

    'add_only_on_end': 'Sólo último nodo',
    'add_only_on_end_tt':
        'Sólo agrega nuevas ramas a los nodos finales. '
        'Árboles como las coníferas suprimen el crecimiento lateral con hormonas. '
        'Efectivamente, esto significa que sólo las yemas laterales muy cercanas a la yema terminal están libres de hormonas y pueden ramificarse.',

    'add_fork': 'Bifurcación',
    'add_fork_tt':
        'Cuando una rama es particularmente fuerte y crece vigorosamente, puede desarrollar varios brotes cerca del final que pueden dominar al brote final. '
        'La rama se divide en varias ramas igualmente vigorosas. '
        'Sin una rama dominante en el centro para empujarlas hacia los lados, '
        'las ramas que se bifurcan crecen a la mitad del ángulo regular. '
        'En lugar de formar un solo tronco claro, un árbol bifurcado crea una estructura de división de las ramas principales.',

    'add_up': 'Hacia arriba',
    'add_up_tt':
        'Gire los yemas añadidos hacia arriba y aléjelos de la gravedad. Gravitropismo negativo para las yemas.',

    'add_regenerate': 'Regenerativas',
    'add_regenerate_tt':
        'Las ramas regenerativas se forman después de una fuerte poda o de un daño natural a lo largo de la rama. '
        'Con menos hojas que sostener, la energía en el exceso de madera da a los viejos brotes dormidos una segunda oportunidad de reparar el árbol y llenar los vacíos. '
        'Muchas coníferas no forman casi ninguna rama regenerativa y necesitan ser podadas cuidadosamente.',

    'add_planar': 'Yemas planas',
    'add_planar_tt': 'Similar al giro horizontal, pero ahora nuevas ramas brotan planas en la dirección del crecimiento.',


    # Grow
    'grow_length': 'Longitud',
    'grow_length_tt': 'Longitud total del nuevo crecimiento',

    'grow_nodes': 'Nodos',
    'grow_nodes_tt':
        'La cantidad máxima de nodos que una rama puede crecer cada año. '
        'Las ramas menos vigorosas desarrollarán menos nodos.',


    # Turn
    'turn_up': 'Hacia arriba',
    'turn_up_tt': 'Gravitropismo negativo. Gira el nuevo crecimiento hacia arriba, lejos de la gravedad.',

    'turn_up_in_shade': 'Cuando sombreada',
    'turn_up_in_shade_tt': 'Gire el crecimiento sombreado hacia arriba y aléjelo de la gravedad.',

    'turn_random': 'Al azar',
    'turn_random_tt':
        'La rama es libre de moverse en direcciones aleatorias e incontroladas sin ser guiada por la luz o la gravedad.',

    'turn_to_light': 'A la luz',
    'turn_to_light_tt':
        'Fototropismo. '
        'Gire el nuevo crecimiento hacia la dirección más luminosa. '
        'Por eso las plantas de interior crecen hacia las ventanas.',

    'turn_to_horizon': 'Al horizonte',
    'turn_to_horizon_tt':
        'Gire el crecimiento de la rama hacia el plano horizontal cuando una rama está sombreada.',


    # Interact

    # Environment is a word with more meanings.
    # Ambiente, Entorno, Alrededores
    'react_enabled': 'Interactúa',
    'react_enabled_tt':
        'Crea objetos de malla para atraer, desviar o detener el nuevo crecimiento. '
        'Haz que un edificio dé sombra, o sé creativo y haz crecer árboles dentro de las formas.',

    'react_block_object': 'Bloquear',  # Bloquear, Obstruir
    'react_block_object_tt': 'Cerrar el paso a las ramas en la colisión con el objeto de entorno.',

    'react_shade_object': 'Sombrar',
    'react_shade_object_tt':
        'El objeto de entorno proyecta sombras en el árbol, influyendo en los parámetros basados en la sombra.',

    'react_deflect_object': 'Desviar',
    'react_deflect_object_tt': 'Evita el objeto de entorno.',

    'react_attract_object': 'Atraer',
    'react_attract_object_tt':
        'El objeto de entorno impone un tropismo positivo a nuevos nodos crecidos, '
        'y ramas pueden crecer libremente a través del objeto.',

    'react_vigor_object': 'Poder',
    'react_vigor_object_tt':
        'Select an object that controls the vigor of new growth.',

    'react_force': 'Fuerza',
    'react_force_tt':
        'La magnitud de la fuerza que el objeto ejerce sobre el árbol.',

    'react_falloff': 'Atenuación',
    'react_falloff_tt':
        'El efecto es más fuerte cerca del objeto y disminuye de manera exponencial con la distancia al objeto.',


    # Thicken
    'thicken_tips': 'Puntas',
    'thicken_tips_tt':
        'Diámetro en los extremos de ramas vigorosas. '
        'Una rama menos vigorosa puede tener un espesor disminuido.',

    'thicken_tips_reduce': 'Reducción',
    'thicken_tips_reduce_tt':
        'Disminuir el espesor de la punta en ramas menos vigorosas. '
        'Una rama menos vigorosa puede tener un espesor disminuido. '
        'Esto afecta la forma del árbol porque las ramas delgadas se doblan más. '
        'Especialmente en las coníferas caídas que suprimen fuertemente sus ramas laterales.',

    'thicken_join': 'Aumenta',  # Ganancia de Espesor
    'thicken_join_tt':
        'Combinar los diámetros de ramas principales y las laterales. '
        'Este importante control tiene una fuerte influencia en la forma de tu árbol. '
        'El espesor se calcula desde el extremo de cada rama hasta la base del árbol. '
        'Cada vez que una rama se encuentra con su superior, '
        'las áreas de ambas secciones transversales se utilizan para calcular el espesor combinado.',

    'thicken_deadwood': 'Madera muerta',
    'thicken_deadwood_tt':
        'This parameter is based on the tube model. When branches drop, their tubes die and this '
        'dead wood area is part of the total area of the cross section.',

    'thicken_base_scale': 'Escala de raíz',
    'thicken_base_scale_tt':
        'Aumentar el espesor en la base. '
        'En la raíz del tronco, aumentar el espesor causado por el crecimiento de las raíces.',

    'thicken_base_shape': 'Forma',
    'thicken_base_shape_tt':
        'Ajusta la forma de la base del árbol.',

    'thicken_base_buttress': 'Protrusiones',
    'thicken_base_buttress_tt':
        'Multiplicar la escala de raíz con protuberancias de raíz.',

    'root_distribution': 'Distribución',
    'root_distribution_tt':
        'Alcance del efecto de la escala de raíz sobre el tronco.',


    # Bend
    'bend_mass': 'Masa',
    'bend_mass_tt':
        'Fuerza de deformación bajo el peso de las ramas.'
        'Valores más altos simulan ramas más pesadas o más flexibles.',

    'bend_twig_mass': 'Masa apical',
    'bend_twig_mass_tt':
        'Cantidad de flexión bajo el peso de hojas. '
        'Las ramitas llevan el peso relativamente grande de sus hojas. '
        'La mayoría de las especies reaccionan a esto con un gravitropismo negativo.',

    'bend_twig_mass_solidify': 'Fijar',
    'bend_twig_mass_solidify_tt':
        'Solidifique la flexión causada por el peso que baja por los extremos de las ramas. '
        'Este peso varía con las estaciones, las flores de primavera pesadas, las hojas grandes y los frutos gruesos tiran de la rama hacia abajo. '
        'Pero cuando llega el momento en que la rama se pone rígida, la mayor parte de este peso ya puede haber caído. '
        'Por lo tanto, este parámetro Solidificar es a menudo menor que el utilizado para solidificar el peso de la rama.',

    'bend_reaction': 'Hacia arriba',
    'bend_reaction_tt':
        'La madera de reacción hace que las ramas de crecimiento fuerte se doblen activamente hacia arriba con el tiempo.',


    # Shade
    'shade_area': 'Área de hojas',
    'shade_area_tt':
        'Zona de proyección de sombras al final de cada rama, en dm². '
        'Un área de hoja de 4.0 es igual a cuatro veces un área de 10cm x 10cm. '
        'Ten en cuenta que este es el área foliar combinada de la ramita, no el área de una sola hoja.',

    'shade_area_reduce': 'Reducción',
    'shade_area_reduce_tt': 'Reduce el área de hojas en las ramas menos vigorosas.',

    'shade_area_depth': 'Profundidad',
    'shade_area_depth_tt':
        'Levanta los lados de las zonas de proyección de sombras para dar más profundidad a la forma. '
        'Esto causará más sombra de los lados del árbol, y más sombra en general. '
        'Puedes compensarlo reduciendo la solteando de ramas sombreadas. '
        'Active la vista previa de la sombra para ver el efecto.',

    'shade_leaf_sides': 'Lados',
    'shade_leaf_sides_tt':
        'Distribuya también zonas de hojas de sombra a los lados de las ramas. '
        'La mayoría de los árboles pueden simularse sólo con las hojas de los extremos de las ramas, '
        'una pequeña abstracción que funciona bien. '
        'Pero en los árboles con ramas lloronas, se necesitan ramitas laterales. '
        'Tenga en cuenta que con esto necesitará un área de hojas más pequeña, ya que se colocarán más ramitas.',

    'shade_branches': 'Ramas',
    'shade_branches_tt': 'La mayoría de la luz es bloqueada por las hojas, pero para algunos árboles se puede incluir la geometría de las ramas en el cálculo de la sombra.',
    'shade_alongside': 'Al lado',
    'shade_alongside_tt': 'Además de ramitas recién crecidas, árboles como los pinos tienen agujas viejas al lado de sus ramas.',
    'shade_alongside_diameter': 'Diámetro',
    'shade_alongside_diameter_tt': 'Diámetro de la geometría que proyecta sombra al lado de las ramas.',

    'shade_branches_panel': 'Ramas',
    'shade_leaves_panel': 'Hojas',

    'tweak': 'Ajusta',
    'tweak_tt': 'Ajusta estos parámetros en la vista, con una visualización en 3D de los cambios.',


    # Build
    'build_resolution': 'Resolución',
    'build_resolution_tt':
        'Número de puntos para describir los perfiles de las ramas. '
        'La resolución en la base del árbol. '
        'Aumente la resolución para agregar detalles o al agregar protuberancias de raíz.',

    'build_resolution_reduce': 'Reducción',
    'build_resolution_reduce_tt':
        'Reducir polígonos en ramas delgadas. '
        'La base del árbol necesita muchos polígonos para obtener un modelo suave. '
        'Pero la mayoría de los polígonos de un árbol están en sus miles de ramas jóvenes. '
        'Estas ramas delgadas pueden hacer con menos polígonos sin perder calidad visual.',

    'smooth': 'Suavizar',
    'smooth_tt':
        'Suavizar nodos agudamente angulados para crear ramas que fluyen suavemente.',

    'texture_bark': 'Corteza',
    'texture_bark_tt':
        'Elige una textura de corteza.',

    'texture_repeat': 'Repetición',
    'texture_repeat_tt':
        'Repite la textura de corteza. '
        'Número de veces que se repite la textura de la corteza alrededor de la circunferencia de la base del árbol. '
        'Se reduce automáticamente en ramas más delgadas.',

    'twig_menu': '',
    'twig_menu_tt':
        'Elige un conjunto de ramitas para agregarlas a tu árbol. '
        'La biblioteca enumera cada ramita que se encuentra en la carpeta de ramas. '
        'Puedes seleccionar una carpeta en las preferencias de usuario de Grove.',

    'twig_pick_objects': 'Escoge objetos de escena',
    'twig_pick_objects_tt': 'Utiliza cualquier objeto en la escena',

    'twig_no_twigs': 'Sin ramitas',
    'twig_no_twigs_tt': 'Sin Ramitas',

    'twig_object_end': 'Larga',
    'twig_object_end_tt':
        'Objeto de ramita para distribuir en extremos de rama.',

    'twig_object_side': 'Corta',
    'twig_object_side_tt':
        'Objeto ramita para distribuir a lo largo de los lados de las ramas.',

    'twig_density': 'Densidad',
    'twig_density_tt':
        'Posibilidad que un nodo de rama tenga una ramita lateral. '
        'Usa esto para controlar la densidad del follaje de tu árbol.',

    'twig_view_detail': 'Detalle en vista',
    'twig_view_detail_tt':
        'Baje la resolución de las ramas. '
        'Para un rendimiento de vista más rápido, esto agrega un modificador Diezmar a cada modelo de ramita. '
        'Las vistas utilizan el modelo de baja resolución modificado - mientras que los motores de render utilizan el original.',

    'twig_pick_collections': 'Colecciones',
    'twig_pick_collections_tt': 'Escoge cualquier colección de objetos de ramitas en el archivo actual.',

    'twig_hide': '',
    'twig_hide_tt': 'Ocultar temporalmente las ramitas para tener una buena vista de la estructura de las ramas.',

    'twig_longevity': 'Límite de edad',
    'twig_longevity_tt':
        'Las ramitas laterales aparecen cerca del final de cada rama, en los nuevos nodos crecidos este año. '
        'La longevidad hace que las ramitas perduren durante más años, manteniéndose en nodos cada vez más viejos. '
        'Esto requiere una reconstrucción para mostrar los cambios.',

    'twig_object_upward': 'Vertical',
    'twig_object_upward_tt':
        'Modelo de ramita opcional que sustituye a la ramita apical cuando crece casi vertical. '
        'Estas ramitas son a menudo aún más largas, y tienen sus hojas retorcidas en todas las direcciones. '
        'Si no ha seleccionado ninguna ramita vertical, se utiliza la ramita apical.',

    'twig_object_dead': 'Muerta',
    'twig_object_dead_tt':
        'Modelo de ramita opcional que se usa en lugar de cualquier otra ramita si la ramita está muerta. '
        'Si no ha seleccionado ninguna ramita muerta, no se utilizará ninguna ramita para las ramitas muertas, lo que dará lugar a menos detalles en las zonas menos vigorosas.',

    'twig_wither': 'Marchitarse',
    'twig_wither_tt':
        'Número de años (después de Vida) que las ramitas muertas se quedan y se marchitan en el árbol. '
        'Reconstruye para ver el efecto.',

    'twig_side_on_tips': 'Laterales en extremo',
    'twig_side_on_tips_tt':
        'Distribuye también ramitas laterales en los extremos de las ramas, '
        'además de las ramas apicales.',

    'language': 'Idioma',
    'language_tt': 'Idioma para usar en la interfaz y descripciones',

    # New
    'grove': 'Arboleda',

    'label_direction': 'Rumbo inicial',
    'panel_auto_prune': 'Poda automática',

    'rebuild': 'Construye',
    'rebuild_tt': 'Reconstruye tus modelos de árboles.',
    'add_new_grove': 'Añade nueva',
    'add_new_grove_tt': 'Añade una nueva colección de grove.',
    'select_a_grove_collection': 'Selecciona una colección de Grove.',
    
    'select_linked_branches': 'Selecciona connectadas',
    'select_linked_branches_tt': 'Expande la selección actual a toda la rama y sus ramas laterales.',
    
    'select_thicker': 'Selecciona gruesas',
    'select_thicker_tt': 'Selecciona geometría que pertenece a nodos de ramas más gruesas, usando el atributo "Thickness".',
    'select_thicker_threshold': 'Umbral',

    'show_dead_preview': 'Mostra muertas',

    # Record
    'record_enabled': 'Graba',
    'record_enabled_tt':
        'Graba el crecimiento como una secuencia de objetos en una colección dedicada llamada Growth. '
        'Cada paso está enmarcado con un fotograma clave para la visibilidad sólo en el fotograma que corresponde con el año que representa.',

    'record_start': 'Fotograma initial',
    'record_start_tt': 'Mueve el inicio de la animación a este número de fotograma.',

    'record_interval': 'Intervalo',
    'record_interval_tt':
        'Cada año es una interpolación fluida de su forma de primavera a la forma de verano. '
        'Defina el número de fotogramas para la interpolación y, por lo tanto, la velocidad de la animación de crecimiento.',

    'disable_outline': 'Esconde contorno',
    'disable_outline_tt':
        'Haga clic para desactivar el sombreado del contorno para una representación correcta del árbol '
        'y una mejor retroalimentación visual al ajustar. El sombreado de contornos hace que las ramas parezcan mucho más gruesas '
        'de lo que realmente son.',

    'set_background': 'Fondo brillante',
    'set_background_tt':
        'Click to brighten up your viewport background and set it to middle gray. '
        'Tree branches will be much easier to see and your trees will look better.',

    'regrow': 'Recrece',
    'regrow_tt':
        'Reinicie y re-crezca rápidamente los árboles hasta la edad actual - omitiendo los pasos de crecimiento interactivos, reconstruyes y oportunidades para podar su árbol.',

    'replant_grove': 'Replantar',
    'replant_grove_tt': '',

    'manual_bend': 'Curva',
    'manual_bend_tt':
        'Una herramienta inspirada en la técnica de los Bonsáis de doblar ramas con alambre de metal, pero mucho más flexible - '
        'se puede doblar cualquier rama sin importar su grosor y sin temor a que se rompa. '
        'Así que mientras que la técnica de los Bonsáis se limita a los árboles pequeños, ahora puedes aplicar los mismos principios para dar forma a los árboles completamente crecidos.',

    'height_info': '{:.1f} m',
    'age_info': '{} ciclos',
    'polygons_info': '{:,} caras',
    'branch_info': '{} rama',
    'branches_info': '{} ramas',

    'label_animating_wind': 'Animando el viento...',
    'label_stop': 'Pare',

    'import_preset': 'Importa archivo...',
    'import_preset_tt':
        'Los ajustes se archivan en un archivo .seed.json que puedes compartir con otras personas - importa alguno para añadirlo a tu lista de ajustes preestablecidos.',

    'placeholder_delay': 'Espera',
    'placeholder_delay_tt': 'Años que el árbol espera antes de empezar a crecer.',

    'add_tree': 'Planta',
    'add_tree_tt':
        'Añade un objeto vacío para empezar a crecer a partir de él. '
        'Mover, rotar, duplicar o eliminar este objeto para que crezcan múltiples árboles comenzando en posiciones específicas, en un ángulo y en grupos.',

    'old_release_warning_line_1': 'Trees grown in old release.',
    'old_release_warning_line_2': 'A lot has changed.',
    'old_release_warning_line_3': 'Use old release to edit.',

    'grow_together': 'Crece juntos',
    'grow_together_tt_short': 'Crece todas las colecciones de arboledas juntas',
    'grow_together_tt':
        'Crece todas las colecciones de arboledas juntas como una sola, '
        'para que puedas mezclar diferentes especies de árboles. '
        'Con cálculos combinados de sombra y fototropismo para que compitan por la luz.',

    'draw': 'Dibuja',
    'draw_tt':
        'Guiar el crecimiento dibujando un camino. '
        'La rama crecerá a lo largo de este camino durante varios años hasta que se recorra todo el camino.',

    'prune_status_draw_lines': 'Dibuja líneas',
    'prune_status_do_prune': 'Poda',

    'bend_tool_distance': 'Distancia',
    'bend_tool_distance_tt': 'Longitud',

    'bend_tool_bend_button': 'Curva',
    'bend_tool_bend_button_tt': 'Aplica la curva',

    'close_button': '',
    'close_button_tt': 'Cierra',

    'turntable': '',
    'turntable_tt': 'Ver',

    'bend_tool_curve': 'Curva',
    'bend_tool_curve_tt': 'La forma de la curva',
    'bend_tool_curve_simple': 'Simple',
    'bend_tool_curve_flexible': 'Flexible',
    'bend_tool_curve_s_curve': 'Curva S',


    # Wind
    'wind_breeze': 'Brisa',
    'wind_breeze_tt':
        'Añade vida a tus ramitas con movimiento animado. '
        'Esto puede funcionar por sí solo para una brisa sutil, '
        'o puedes combinarlo con la animación de viento para un viento más fuerte.',

    'label_wind': 'Viento',

    'calculate_wind': 'Anima viento',
    'calculate_wind_tt': 'Calcula la animación del viento',

    'wind_vector': 'Viento',
    'wind_vector_tt': 'Velocidad y dirección del viento',
    'wind_turbulence': 'Turbulencia',
    'wind_turbulence_tt':
        'Levanta las ramitas y haz que las ramas bailen al viento.',

    'wind_shapes': 'Duración',
    'wind_shapes_tt':
        'Formas clave, una para cada dos fotogramas.',

    'grow_tool_growing': 'Creciendo',
    'grow_tool_growing_tt': 'Esc para cancelar.',
    'grow_tool_building': 'Construyendo',

    # Plant operator.
    'plant_layout': 'Disposición ',
    'plant_layout_tt': 'Plantar un huerto frutal, una plantación, un seto, un anillo o grupos naturales de árboles',

    'plant_trees': 'Árboles',
    'plant_trees_tt': 'La cantidad de árboles.',

    'plant_space': 'Espacio',
    'plant_space_tt': 'La distancia entre los árboles',

    'plant_random_seed': 'Semilla aleatoria',
    'plant_random_seed_tt': 'Colocación aleatoria',

    'plant_delay': 'Retraso',
    'plant_delay_tt': 'Los árboles más alejados del centro comienzan a crecer más tarde.',

    'plant_random_shift': 'Al azar',
    'plant_random_shift_tt': 'Aleatorizar la ubicación de cada árbol',

    'plant_ring_radius': 'Radio',
    'plant_ring_radius_tt': 'La distancia desde el centro del anillo',

    'plant_rows_trees_tt': 'El número de árboles por fila',

    'plant_rows': 'Filas',
    'plant_rows_tt': 'El número de filas',

    'plant_rows_space': 'Espacio',
    'plant_rows_space_tt': 'La distancia entre filas',

    'plant_rows_diagonal': 'Diagonal',
    'plant_rows_diagonal_tt': 'Disposición tresbolillo',

    'plant_islands_trees_tt': 'Número medio de árboles por isla',

    'plant_islands': 'Islas',
    'plant_islands_tt': 'Número de islas de árboles',

    'plant_islands_space': 'Epacio entre islas',
    'plant_islands_space_tt': 'Distancia media entre islas de árboles',

    'plant_islands_clearing': 'Despejando',
    'plant_islands_clearing_tt': 'Despejando en el bosque',

    'plant_islands_randomize_tt':
        'Aleatorizar el espacio entre los árboles, las islas y el número de árboles por isla',

    'plant_layout_clump': 'Grupo',
    'plant_layout_rows': 'Filas',
    'plant_layout_ring': 'Anillo',
    'plant_layout_islands': 'Islas',

    'plant_variation_panel': 'Variación',
    'plant_diverge': 'Diverge',
    'plant_diverge_tt': 'Gire en sentido contrario a los árboles cercanos.',

    'plant_terrain_panel': 'Terreno',
    'plant_terrain_drop': 'Caer',
    'plant_terrain_drop_tt': 'Project trees to the ground.',

    'plant_terrain_slope': 'Inclinación',
    'plant_terrain_slope_tt': 'Adopta la inclinación del terreno en la rotación del árbol.',

    'escape_to_stop': 'Escape para parar',

    'surround_enabled': 'Alrededor',
    'surround_enabled_tt':
        'Simule la sombra de árboles circundantes, sin tener que cultivar un bosque completo.'
        'Haz clic en el círculo para ajustar los parámetros de forma interactiva.',
    'surround_density': 'Densidad',
    'surround_density_tt':
        'Cultive su árbol en un campo abierto o en un bosque denso, o en cualquier lugar intermedio.',
    'surround_height': 'Altura',
    'surround_height_tt':
        'Una altura fija que se puede utilizar para los árboles o edificios circundantes ya establecidos. '
        'Utilice la altura automática para que el entorno crezca junto con sus árboles.',
    'surround_grow': 'Creciendo',
    'surround_grow_tt':
        'La altura aumenta automáticamente cada año: los árboles circundantes crecen junto con los tuyos.',
    'surround_distance': 'Distancia',
    'surround_distance_tt': 'Espacio libre para crecer.',

    'widget_scale': 'Escala de widgets',
    'widget_scale_tt':
        'Ajusta el tamaño de los widgets si aparecen demasiado pequeños o grandes en tu pantalla.',


    # File
    'file': 'Guarda',
    'file_tt': 'Guarda y recupera tus árboles.',

    'file_recent': 'Archivo reciente',

    'file_import': 'Importa árboles',
    'file_import_tt': 'Importa una simulación desde un archivo .grove.',

    'file_export': 'Exporta árboles',
    'file_export_tt': 'Exporta la simulación actual a un archivo .grove.',


    # Roots
    'roots': 'Raíces',
    'roots_tt':
        'Generar raíces superficiales. '
        'Las raíces crecen normalmente bajo tierra, pero pueden quedar expuestas por la erosión del suelo. '
        'Estéticamente atractivas, sirven para fijar el árbol al suelo.',

    'roots_roots_panel': 'Raíces',
    'roots_number': 'Numero',
    'roots_number_tt': 'El numero de raíces.',
    'roots_nodes': 'Nodos',
    'roots_nodes_tt': 'El número de nodos por raíz.',
    'roots_length': 'Longitud',
    'roots_length_tt': 'La longitud entre dos nodos.',
    'roots_climb': 'Escala',
    'roots_climb_tt': 'Haz que las raíces suban a lo largo del tronco para crear una transición suave.',
    'roots_turn_down': 'Hacia abajo',
    'roots_turn_down_tt': '',

    'roots_branches_panel': 'Raíces laterales',
    'roots_branches_panel_tt': '',
    'roots_generations': 'Generaciones',
    'roots_generations_tt': 'Aumenta las generaciones para añadir más detalles al sistema de raíces.',
    'roots_density': 'Densidad',
    'roots_density_tt':
        'Posibilidad de cultivar una sub-raíz. '
        'Para aumentar aún más la densidad, aumentar el número de nodos y reducir la longitud.',
    'roots_add_angle': 'Ángulo',
    'roots_add_angle_tt': 'El ángulo desde la raíz principal.',
    'roots_add_down': 'Hacia abajo',
    'roots_add_down_tt': 'Empieza a crecer con un ángulo hacia abajo.',

    'roots_variation_panel': 'Al azar',
    'roots_random_heading': 'Rumbo',
    'roots_random_heading_tt': 'Crecer en direcciones aleatorias a través del suelo.',
    'roots_random_pitch': 'Inclinación',
    'roots_random_pitch_tt': 'Crecer aleatoriamente hacia arriba y hacia abajo.',
    'roots_random_seed': 'Semilla aleatoria',
    'roots_random_seed_tt': 'Generar una variación distinta.',

    'roots_thickness_panel': 'Grosor',
    'roots_thickness': 'Grosor',
    'roots_thickness_tt': 'Grosor medio de una raíz principal.',
    'roots_thickness_reduce': 'Reducción',
    'roots_thickness_reduce_tt': '',
    'roots_thickness_random': 'Al azar',
    'roots_thickness_random_tt': '',

    'roots_terrain_panel': 'Terrain',
    'roots_terrain_panel_tt': '',
    'roots_drop': 'panel_drop',
    'roots_drop_tt': '',

    'restart_all': 'Reinicie todas',
    'restart_all_tt': 'Reinicie todas las arboledas.',

    'restart_single_tree': 'Sólo un árbol',
    'restart_single_tree_tt': 'Elimina los marcadores de posición y planta un solo árbol en el origen.',

    'restart_revert': 'Empezar de nuevo',
    'restart_revert_tt':
        'Reinicia todos los parámetros a su valor predeterminado, '
        'recarga el preajuste activo y reinicia con un solo árbol.',

    'operator_turntable': 'Turntable',
    'operator_turntable_tt': 'View your trees from eye level - walk around and under the canopy.',

    'stake_enabled': 'Tutor',
    'stake_enabled_tt': 'Una estaca ayuda a que el tronco crezca recto.',
    'stake_height': 'Altura',
    'stake_height_tt': 'Hasta esta altura, un tutor evita que el árbol se curve, asegurando que crezca de forma recta.',

    'plant': 'Planta',
    'plant_tt':
        'Planta un grupo de árboles: crea huertos, setos o islas naturales de árboles. '
        'Esta herramienta crea objetos vacíos que puedes mover libremente, duplicar o eliminar.',

    'build_skeleton': 'Construye esqueleto',
    'build_skeleton_tt':
        'Crea huesos, grupos de pesos de huesos y viento.',

    'skeleton': 'Esqueleto',
    'skeleton_tt':
        'Crea un esqueleto que te permita animar árboles utilizando huesos. '
        'También añade grupos de vértices para vincular puntos de malla a sus respectivos huesos. '
        'Opcionalmente añade animación de viento a los nuevos huesos.',

    'skeleton_reduce': 'Reduce',
    'skeleton_reduce_tt':
        'Cree menos huesos omitiendo las ramas laterales delgadas.',
    
    'skeleton_panel_bones': 'Huesos',
    'skeleton_panel_wind': 'Viento',

    'skeleton_bias': 'Sesgo',
    'skeleton_bias_tt':
        'Aumenta para añadir más huesos arriba, disminuye para añadir más huesos abajo.',

    'skeleton_length': 'Longitud',
    'skeleton_length_tt':
        'Crea huesos más largos saltando nodos.',

    'skeleton_connected': 'Conectado',
    'skeleton_connected_tt':
        'Algunos programas requieren conexiones para crear una jerarquía, '
        'mientras que otros permiten que los huesos sean superiores de huesos completamente separados. '
        'Hacer estas conexiones aumentará el número de huesos.',
    
    'sow_enabled': 'Sembra',
    'sow_enabled_tt': 'Dispersa semillas alrededor de árboles existentes para simular un bosque de árboles que se extiende naturalmente.',
    
    'sow_age': 'Demora',
    'sow_age_tt': 'Los árboles tardan varios años en arraigar y establecer un estado energético positivo antes de empezar a producir semillas.',
    
    'sow_chance': 'Probabilidad',
    'sow_chance_tt':
        'Cada año, cada árbol tiene una posibilidad de añadir un nuevo árbol.'
        'En realidad, algunos árboles pueden crear miles de semillas, y cientos de estas semillas pueden germinar cada año.'
        'Pero casi ninguna sobrevive para crecer como un árbol apropiado.'
        'Para mantener la simulación funcionando a una velocidad óptima, mantén baja la probabilidad.',
    
    'sow_distance': 'Distancia',
    'sow_distance_tt': 'Las semillas se dispersan dentro de una distancia alrededor de los árboles existentes.',
    
    'sow_limit': 'Límite',
    'sow_limit_tt':
        'El número máximo de árboles. Deja de añadir nuevos árboles más allá de este número para mantener la simulación funcionando a una velocidad óptima.',
    
    'build_triangulate': 'Triangular',
    'build_triangulate_tt': 'Utiliza solo triángulos para construir las ramas del árbol, sin cuadriláteros.',
    
    'build_cutoff_thickness': 'Corte de grosor',
    'build_cutoff_thickness_tt': 'Omite la construcción de nodos por debajo de este diámetro.',
    
    'build_cutoff_age': 'Corte de edad',
    'build_cutoff_age_tt':
        'El nivel de detalle omite la construcción de los últimos años de crecimiento para reducir drásticamente el número de polígonos. '
        'Esto debe compensarse con ramitas más grandes que representen un número igual de años de crecimiento.',
    
    'build_blend': 'Conexiones fluidas',
    'build_blend_tt':
        'Añade nodos adicionales para crear una transición suave desde la rama principal. '
        'Esto siempre se hace en ramas más gruesas, pero puede desactivarse para ramas más delgadas y reducir dramáticamente el número de polígonos.',
    
    'build_end_cap': 'Terminaciones',
    'build_end_cap_tt':
        'Cierra los extremos de las ramas con polígonos que conectan a un punto extendido. '
        'Elimina las tapas para una reducción considerable en el número de polígonos, lo que es casi invisible cuando se usan ramitas o a una distancia moderada.',
    
    'detail_simplify': 'Simplificar',
    'detail_simplify_tt':
        'Simplifica las ramas omitiendo nodos rectos con casi ningún cambio en la dirección. '
        'Esto proporciona solo una modesta reducción en el número de polígonos.',

    # Old and unused
    'shade_avoidance': 'Evita sombra',
    'shade_avoidance_tt':
        'Aumenta o disminuye Prioriza Corriente en ramas sombreadas. '
        'Con la evitación de sombra, cada rama controla su propia Prioriza Corriente, como estrategia para encontrar luz. '
        'Cuanto más sombreada está una rama está, puede favorecer su crecimiento corriente en busca de luz, '
        'o puede favorecer el crecimiento de la rama secundaria con el fin de tomar la luz que puede obtener en la sombra. '
        'Esto último se puede ver en especies como la Haya o el Avellano.',

    'shade_elongation': 'Más cuando sombreada',
    'shade_elongation_tt':
        'Ramas sombreadas crecen más o menos. '
        'Plantas que crecen en la sombra crecerán más largas con la esperanza de encontrar luz. '
        'Junto con una reducción en el espesor, esto crea ramas más largas pero más débiles que se doblan más. '
        'Puedes iniciar las ramas colgantes que se ven a menudo en la parte inferior de la copa.',

    'wind_frequency': 'Frecuencia del viento',
    'wind_frequency_tt':
        'Frecuencia del viento',

    'label_layers': 'Capas',

    'branching_inefficiency': 'Ineficiencia',
    'branching_inefficiency_tt':
        'Una forma directa de limitar el poder de crecimiento de sub-ramas y sus sub-ramas consecutivas. '
        'Una conexión de ramificación es imperfecta y limita el transporte de agua.',

    'sapwood': 'Madera albura',
    'sapwood_tt':
        'Espesor de madera viva. Es la madera viva que transporta el agua. '
        'El núcleo de la rama en su interior es de madera muerta y sólo actúa como una estructura de '
        'soporte, llamada duramen. El aumento de este valor resultará en una menor acumulación de espesor '
        'en ramas más gruesas.',

    'Placeholder': 'Placeholder',

    'shade_sensitivity': 'Sensbilidad',
    'shade_sensitivity_tt':
        'La sensibilidad de un árbol a sombrearse. '
        'Sombra es un valor lineal desde luz a oscuridad, '
        'pero procesos naturales a menudo tienen reacciones exponenciales. '
        'Disminuirlo a cero para una reacción lenta a la sombra, '
        'sólo después de que una rama recibe sombra substancial, responderá. '
        'Aumentarlo a uno para una reacción inmediata, '
        'la más leve sombra será ampliada fuera de proporción.',
    
    'close': 'Cierra',
    
    "use_scientific_names": "Nombres Científicos",
    "use_scientific_names_tt": 
        "Mostrar especies de ramitas usando sus nombres científicos, cuando estén disponibles. "
        "Cuando está desactivado, el menú de ramitas muestra el nombre común en inglés.",
    
    "plant_islands_randomize": "Aleatorio",
    "plant_islands_randomize_tt": "Variar el número de árboles por isla",
    
    "fallback_instructions": "Prepárate para crecer",
    "fallback_instructions_tt": "Sigue las instrucciones en http://www.thegrove3d.com/info/install/ para instalar el núcleo de simulación.",
    
    "trial_end": "Comprar Ahora...",
    "trial_end_tt": "Tu prueba ha expirado. Si te gusta The Grove, por favor compra una licencia para seguir creando árboles increíbles."
}
