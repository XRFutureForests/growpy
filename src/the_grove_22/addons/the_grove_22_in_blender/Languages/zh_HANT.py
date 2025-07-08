# coding=utf-8

dictionary = {

    '': '',

    # Panel titles
    'panel_presets': '預設',
    'panel_simulation': '模擬',
    'panel_favor': '偏重',
    'panel_drop': '墜落',
    'panel_add': '增添',
    'panel_grow': '生長',
    'panel_turn': '轉動',
    'panel_react': '反應',
    'panel_thicken': '變粗',
    'panel_bend': '彎曲',
    'panel_shade': '遮光',
    'panel_build': '構建',
    'panel_build_texture': '紋理',
    'panel_build_wind': '風',
    'panel_twigs': '拾取枝葉',


    # User preferences
    'set_twigs_path': '設置枝葉檔夾...',
    'twigs_path': '枝葉檔夾',
    'twigs_path_tt': '指向您將枝葉存儲其中的檔夾. 這些枝葉會被羅列在枝葉拾取器中.',
    'set_textures_path': '設置紋理檔夾...',
    'textures_path': '樹皮紋理檔夾',
    'textures_path_tt': '指向您將樹皮紋理存儲其中的檔夾. 這些紋理會被羅列在紋理拾取器中.',


    # Interface messages
    'remove_preset_info': '要移除{}嗎?',
    'overwrite_preset_info': '要覆蓋{}嗎?',
    'name_preset_info': '命名您的預設.',
    'height_info': '{:.1f}米',
    'age_info': '{}年',
    'branch_info': '{}根枝幹',
    'branches_info': '{:,}根枝幹',
    'polygons_info': '{:,}個面',
    'tips_info': '請閱讀工具提示:',

    "tweak": "調整",
    "tweak_tt": "在視圖中調整這些參數，並顯示更改的可視化.",


    # Presets
    'presets_menu': '',  # Read
    'presets_menu_tt': '加載樹種的預設參數',

    'preset_name': '新名稱',
    'preset_name_tt': '指保存或覆蓋的預設名稱',

    'remove_preset': '移除',
    'remove_preset_tt': '移除此預設',

    'cancel_action': '取消',

    'remove_preset_confirm': '移除',
    'remove_preset_confirm_tt': '確認移除此預設',

    'rename_preset': '重命名',
    'rename_preset_tt': '重命名此預設',

    'add_preset': '添加',
    'add_preset_tt': '添加一種新預設, 或是在某一預設名稱已存在的情況下替換該預設.',

    'overwrite_preset': '覆蓋',
    'overwrite_preset_tt': '覆蓋此預設',

    'overwrite_preset_confirm': '覆蓋',
    'overwrite_preset_confirm_tt': '確認替換此預設',

    'save_preset': '保存',
    'save_preset_tt': '將當前屬性保存為預設',


    # Simulate
    'simulation_flushes': '年輪',
    'simulation_flushes_tt':
        '新增應生長年數. '
        '採用小的交互步驟模擬您的樹木. '
        '每一步之後您都可以通過剪枝操作來操縱您的樹木, '
        '甚至可能還會用到調整樹木參數, 或是改變其生長所處的環境.',

    'zoom': '縮放',
    'zoom_tt': '進行縮放為的是在視窗中適配整個樹木',

    'simulate': '生長',
    'simulate_tt':
        '生長您的樹木. '
        '通過採用交互步驟生長, 轉動, 彎曲, 流動和剪枝來模擬四季. '
        '觀看您的樹木一年又一年的成長.',

    'restart': '重新開始',
    'restart_tt':
        '移除樹木並重新開始. '
        '調整您的樹木的樹體特徵經常是一個反復試驗的過程. '
        '即使您的設置全都完全正確時, 大自然又會不夠完美. '
        '生長, 調整, 重新開始, 重複..., 這就是生長樹木的方式.',

    'manual_prune': '剪枝',
    'manual_prune_tt':
        '在視窗中繪製出切割線可移除或縮短枝幹.',

    # Flow
    'favor_end': '末端',
    'favor_end_tt':
        '[偏重末端]給予枝幹末端的是完全覆蓋新側枝的[頭部開始]. '
        '[頭部開始]會創造出先從其開始的較為短小, 強度不大的側邊枝葉來, 不過[頭部開始]並不一定是穩贏的一方. '
        '[偏重光亮]接替, 會慢慢轉變於最佳表現群體有利的勝算 - '
        '目的是使短小的側邊枝葉能夠趕上來甚至是作為新的主導枝幹來接替. '
        '[偏重光亮]和[偏重末端]是最為重要的樹體特徵中的兩個. '
        '它們共同發揮著作用, 可創造出廣泛的形狀和樹體特徵.',

    'favor_bright': '光亮',
    'favor_bright_tt':
        '將樹木的枝葉想像成無數的個體植物. '
        '光亮變大, 黑暗消失 - 這是最完全狀態的[偏重光亮]. '
        '現在將這些植物與枝幹相連 - 為的是賦予它們一種分享自身獲益的方式. '
        '當糖分能自由流動且光照充足時, 哪怕被遮光的植物也將能夠獲得自身生長和尋找新光照所需的供養.',

    "favor_end_reduce": "減少",
    "favor_end_reduce_tt":
        "當樹枝以垂直角度生長時，減少頂端優先的影響。",

    'favor_rising': '上升',
    'favor_rising_tt':
        '對向上生長枝幹的偏重超過了那些垂下來的枝幹. '
        '向上促進枝幹可獲得高聳的樹木. '
        '值為1時會盡可能地將水準枝幹的強度降低至零.',

    # Drop
    'auto_prune_low': '低的',
    'auto_prune_low_tt':
        '修剪低於此高度的低懸枝幹. '
        '自動剪枝城市用樹的基部以便允許行人和交通自由通行. '
        '墜落地面霜損毀的低懸枝幹. 或是墜落被覓食動物奪走了的枝幹. '
        '當樹木生長的較高時此剪枝操作會逐漸開始生效.',

    'auto_prune_keep_thick': '保留粗大的',
    'auto_prune_keep_thick_tt':
        '只剪枝較細小的枝幹而保留較粗大的枝幹. '
        '此參數將允許樹木生長出若干根大的主枝幹, 從而為您的樹木賦予更自然的觀感. '
        '一種園藝工作者在剪枝擁有更多空間的樹木時所追求的觀感, 比如公園中的. '
        '這種現象也發生在自然界, 覓食的動物瞧不上粗大的枝幹, 而是更為喜歡新鮮多汁的枝幹.',

    'drop_shaded': '被遮光嫩枝',
    'drop_shaded_tt':
        '墜落被遮光的枝幹. '
        '每年樹木都會在各個方向上生長出數不盡的新枝葉來. '
        '這些敏感的小枝幹會探索新空間和尋找光照. '
        '然後樹木就會將其能量只投入進光亮的枝葉中, 同時還將墜落許多被遮光的枝葉. '
        '減小此參數可保留更多枝幹, 然後生長出濃密的樹木來. '
        '將此參數向1增加可墜落更為光亮的枝幹, 然後生長出透亮散開的樹木來.',

    'drop_decay': '暫時存留',
    'drop_decay_tt':
        '將死亡的枝幹留在樹上. '
        '死亡的枝幹腐爛並從樹上脫落需要一些時間.'
        '尤其針葉樹較低的軀幹, 全都佈滿了死亡的枝幹.',

    'drop_weak': '低強度末端',
    'drop_weak_tt':
        '指低於枝幹末端結出花朵並停止長度上的生長的生長強度. '
        '高強度的枝幹在這裏用來使樹木生長到新的高度. '
        '較低強度的枝幹末端被賦予了結出花朵和果實的新用途. '
        '此參數會結束枝幹在長度上的生長, 從而允許側枝來接替. '
        '較高的值會增加開花的幾率. ',

    'drop_obsolete': '廢棄',
    'drop_obsolete_tt':
        '隨著樹木的生長, 較低的枝幹會被遮光, 小枝幹也會因此而墜落. '
        '老的主枝幹會比供養自身逐漸減少的樹葉所需的那些枝幹要粗大. '
        '此類附加木材無法得到供養, 枝幹最終會廢棄, 腐爛然後墜落.'
        '重度手工剪枝之後也會出現這種情況.',


    # Add
    "add_side_branches": "芽",
    "add_side_branches_tt":
        "每個節點的芽數直接影響分支的幾何排列，其中交替、對生"
        "和輪生模式分別對應一個、兩個和三到六個芽。"
        "生長活力與機會共同決定這些芽中有多少會實際發展成新的分支。",
    
    'add_chance': '幾率',
    'add_chance_tt':
        '指年短節點產生新枝幹的幾率. '
        '並不是所有的芽都會開放並生長出新枝幹. '
        '有一些被霜凍或昆蟲毀壞了, 還有一些被[偏重主流]抑制了.',

    "add_chance_reduce": "減少",
    "add_chance_reduce_tt": "降低向不那麼旺盛的分支添加新側枝的機會。減少側枝的添加將使這些分支積累較少的厚度。最後，這將使較低的遮陽分支並彎曲至地面.",

    'add_regenerate': '再生',
    'add_regenerate_tt':
        '重度剪枝或自然毀壞之後會沿著枝幹附加地結出再生嫩枝來. '
        '在缺少樹葉供養的情況下, 附加木材中的能量會令老的休眠芽獲得二次修復樹木和填補間隙的機會.'
        '針葉樹種很少會結出再生嫩枝來.',

    'add_bud_life': '芽壽命',
    'add_bud_life_tt':
        '對大部分樹種而言, 芽只會存活幾年. '
        '達到此年齡的芽是能夠生長出新枝葉的.'
        '而對於另外的樹種而言, 幾乎每一個芽都會開放, 並且基本上都會結出非常短小的, 受頂端優勢限制的枝葉來. '
        '這些枝葉中的大部分會很快死去, 而其中的少數枝葉則會擺脫抑制, 生長成新的枝幹.',

    'add_only_on_end': '僅在末端上',
    'add_only_on_end_tt':
        '只為末端節點添加新枝幹. '
        '像針葉樹這類樹木會抑制激素的側向生長. '
        '實際上這意味著只有那些非常靠近末端的節點才沒有激素, 也才能夠結出新枝幹來.',

    'add_fork': '分叉',
    'add_fork_tt':
        '當某一枝幹十分強壯且長勢旺盛時, 其就能在可壓制尾結的末端附近長出來若干個芽. '
        '於是枝幹就會拆分成若干根強度均等的枝幹. 對於中間沒有主導枝幹的情況, 為了將拆分成的枝幹推到側邊, 分叉的枝幹會按常規角度的一半來生長. '
        '分叉的樹木不會形成完全單一的軀幹, 而是會創造出散開型的主枝幹結構來.',

    'add_horizontal': '水準',
    'add_horizontal_tt':
        '芽的斜向性. '
        '葉序角朝著水準取向的轉向.',

    'add_angle': '角度',
    'add_angle_tt':
        '指新枝幹及其父枝幹間的角度. '
        '角度範圍是從枝幹的直線延長線到垂直於父枝幹方向的[0° - 90°]間的角.',

    'add_twist': '扭轉',
    'add_twist_tt':
        '扭轉每個接連的節點. '
        '像七葉樹這類樹種在沿著它們枝幹的長度上有非常明顯的扭轉, '
        '您可以在軀幹周圍清楚地看到向上打旋兒的樹皮圖案. '
        '除了明顯的視覺品質, 扭轉還會增加芽的葉序旋轉. '
        '此參數會改善相對分枝的樹木上的枝幹分佈.',


    # Grow
    'grow_length': '長度',
    'grow_length_tt': '指新生長的總長度',

    'grow_nodes': '節點',
    'grow_nodes_tt':
        '枝幹每年能生長的最大節點數量. 低強度的枝幹會生長較少的節點.',


    # Turn
    'turn_up': '向上',
    'turn_up_tt': '反向向重力性. 將新的生長轉為向上, 遠離重力. 改用負值可向下生長.',

    'turn_up_in_shade': '陰影處向上',
    'turn_up_in_shade_tt': '將被遮光的生長轉為向上, 遠離重力. 改用負值可向下生長.',

    'turn_to_light': '向光',
    'turn_to_light_tt':
        '向光性. '
        '將新生長轉向最光亮的方向. '
        '這是種使室內植物朝著窗戶生長的效果. '
        '對於樹木而言, 此效果會改善其枝幹的分佈.',

    'turn_to_horizon': '向地平線',
    'turn_to_horizon_tt':
        '斜向性. '
        '當枝幹被遮光時將枝幹的生長轉向水平面.',

    "turn_random": "隨機",
    "turn_random_tt": "分支可以自由地沿著隨機、不受控制的方向移動，不受光線或重力的引導.",


    # Interact
    'react_block_object': '阻斷',
    'react_block_object_tt':
        '與環境對象碰撞之後停止生長.',

    'react_shade_object': '陰影',
    'react_shade_object_tt':
        '環境對象會投下陰影, 從而影響那些依賴光照的參數.',

    'react_deflect_object': '偏轉',
    'react_deflect_object_tt': '避開環境對象.',

    'react_attract_object': '吸引',
    'react_attract_object_tt':
        '朝著環境對象生長. '
        '枝幹能穿過對象自由生長.',

    'react_vigor_object': '強度',
    'react_vigor_object_tt':
        '選擇一種能控制新生長的活力的對象.',

    "react_force": "力量",
    "react_force_tt":
        "物體對樹木施加的力量大小.",

    "react_falloff": "衰减",
    "react_falloff_tt":
        "效果在物體附近更強，在物體距離上呈指數衰減.",


    # Thicken
    'thicken_tips': '末梢',
    'thicken_tips_tt':
        '指枝幹末端的直徑. '
        '這是枝幹具有滿強度時的末梢粗細. '
        '較低強度的枝幹可以擁有減小了的粗細.',

    'thicken_tips_reduce': '減小',
    'thicken_tips_reduce_tt':
        '減小低強度枝幹處的末梢的粗細. '
        '低強度的枝幹生長的會更細小. '
        '此參數會影響樹木的形狀, 原因是細枝幹會彎曲的很厲害. '
        '尤其會影響大量抑制其側枝的下垂針葉樹的形狀.',

    'thicken_join': '連接枝幹',  # Grow or Merge or Join or Reinforce
    'thicken_join_tt':
        '生長的更為粗大. '
        '粗細是從尖梢開始被增加的. '
        '每當兩個枝幹連接時, 兩者的交叉部分都會相加, 為的是創造出更粗壯的枝幹來. '
        '這種行為會一路持續到樹木的基部. '
        '改變枝幹在粗細上的生長速度將會明顯改變您的樹木的形狀. '
        '增加了的粗細會強化枝幹並減少彎曲.',

    'thicken_base_scale': '基部比例',
    'thicken_base_scale_tt':
        '增加基部處的粗細. '
        '在軀幹的根部, 增加根部生長所造成的粗細.',

    'thicken_base_shape': '形狀',
    'thicken_base_shape_tt':
        '調整[根比例]緩慢融入軀幹的形狀.',

    'thicken_base_buttress': '根突',
    'thicken_base_buttress_tt':
        '指帶有根突體的多樣[根比例].',

    'root_distribution': '分佈',
    'root_distribution_tt':
        '指遍佈軀幹之上的[根比例]效應的到達率.',


    # Bend
    'bend_mass': '枝幹彎曲量',
    'bend_mass_tt':
        '指迫於枝幹重量而彎曲的效果量. '
        '枝幹的彎曲會對樹木的形狀造成巨大影響, 特別是長成年長枝幹的情況下更是如此. '
        '枝幹會彎曲多少取決於自身的粗細 - '
        '較粗大的枝幹重量就越大, 不過在對抗重力方面, 增加的交叉部分能令它們以指數形式變得更為強壯.',

    'bend_twig_mass': '枝幹末端彎曲量',
    'bend_twig_mass_tt':
        '指迫於葉子重量而彎曲的效果量. '
        '枝幹末端會承載相對較重的重量, 這些重量來自它們那些長滿葉子, 花朵和果實的枝葉. '
        '樹木會借助反向向重力性通過向上生長來儘量反抗此彎曲. '
        '彎曲和向重力性間的相互影響對於帚狀樹體特徵或垂枝型樹體特徵的形成都發揮著重要作用.',

    'bend_reaction': '反應',
    'bend_reaction_tt': '反應木材會令長勢強勁的枝幹隨著時間的推移主動向後彎曲.',


    # Shade
    'shade_area': '葉面積',
    'shade_area_tt':
        '指每個枝幹末端處的陰影投射面積, 以dm²為單位. '
        '值為4.0的[葉面積]等於值為10cm x 10cm的面積的4倍. '
        '請注意, 這是枝葉的複合葉面積, 不是單個葉子的面積.',

    'shade_area_depth': '深度',
    'shade_area_depth_tt':
        '上提陰影投射器的側邊可增大形狀的深度. '
        '這樣做會致使樹木的側邊投射出較多的陰影, 整體的陰影也會因此而變多. '
        '您可以通過減少下落遮光的方式進行補償. '
        '啟用陰影預覽可查看效果.',

    'shade_leaf_sides': '側邊',
    'shade_leaf_sides_tt':
        '沿枝幹的側邊也會分佈遮光葉面積. '
        '枝幹末端處有葉子, 再加上很少一部分表現力不錯的抽象概念就能模擬大部分樹木. '
        '但是在那些帶有垂枝型枝幹的樹木上是需要有側枝的. '
        '請注意, 這種情況您需要使用較小的葉面積, 因為將會有更多的枝葉被放置.',

    'shade_area_reduce': '減少',
    'shade_area_reduce_tt': '減小較低強度的枝幹上的葉面積.',


    # Build

    'build_resolution': '解析度',
    'build_resolution_tt':
        '指樹木的基部(位於其最粗大的部位)處的頂點數量.',

    'build_resolution_reduce': '縮減',
    'build_resolution_reduce_tt':
        '縮減較細小枝幹處的多邊形. '
        '樹木的大部分多邊形都位於其無數的年短枝幹裏. '
        '在不損失視覺品質的情況下這些細枝幹可以使用較少的多邊形.',

    'smooth': '平滑',
    'smooth_tt':
        '減小尖角的角度可創建更為平滑彎曲的枝幹.',

    'texture_bark': '樹皮紋理',
    'texture_bark_tt':
        '拾取紋理',

    'texture_repeat': 'UV重複',
    'texture_repeat_tt':
        '指圍繞樹木基部的周長重複樹皮紋理的次數 - '
        '在較細小的枝幹處就自動減少了.',

    'wind_frequency': '風頻率',
    'wind_frequency_tt':
        '指風的頻率.',

    'simulation_scale':
        '按比例縮放',
    'simulation_scale_tt':
        '使預設適應不同的枝葉大小. '
        '一個普通的枝葉包含1年或2年的生長, 有大約30cm長. '
        '預設被設計用來匹配此大小. 不過枝葉模型可以是您想要的任意大小, 從單葉一直到有數年生長的都可以. '
        '匹配不同大小的枝葉的方式就是簡單地按比例放大或縮小枝幹模型. '
        '此操作會按同一真實比例保留您的枝葉.',

    'twig_menu': '枝葉',  # Twigs, Library, Pick
    'twig_menu_tt':
        '拾取一組枝葉以便將它們添加到您的樹木上. '
        '此菜單列舉出了能在枝葉檔夾中找到的每一種枝葉 - '
        '您可以在Grove的用戶首選項中選擇檔夾. '
        '或者還可以從當前場景拾取對象.',

    'twig_pick_objects': '場景對象',
    'twig_pick_objects_tt': '拾取場景中的任意3D對象.',

    'twig_no_twigs': '無枝葉',
    'twig_no_twigs_tt': '沒有枝葉',

    'calculate_wind': '設置動畫',
    'calculate_wind_tt': '為您的樹木添加風動畫.',

    'twig_object_end': '末端',
    'twig_object_end_tt':
        '指在枝幹末端處分布的枝葉對象. '
        '末端枝葉是指帶有葉子, 有時是花朵和後結果實的全新生長. '
        '末端枝葉是現有枝幹的延伸 - 往往比側邊枝葉要強壯的多, 長的多.',

    'twig_object_side': '側邊',
    'twig_object_side_tt':
        '指沿著枝幹的側邊分佈的枝葉對象. '
        '側邊枝葉是指沿現有枝幹的側邊長出來的全新枝幹. '
        '它們攜帶有葉子, 有時是花朵和後結果實. '
        '側邊枝葉往往比末端枝葉要短, 這是產生它們的主導枝幹存在激素抑制所致.'
        '最終只有最強壯的枝葉才會長成全新的枝幹.',

    'twig_density': '密度',
    'twig_density_tt':
        '通過添加或多或少的側邊枝葉來控制您樹木的樹葉密度.',

    'twig_view_detail': '視圖細節',
    'twig_view_detail_tt':
        '降低枝葉的顯示解析度. '
        '為了獲得更好的視窗性能, 此參數會為每個枝葉模型都添加[精簡]修改器. '
        '視窗會使用修改了的低解析度模型 - 針對渲染引擎使用原始模型的情況.',

    'use_adaptive_units': '使用自適應單位',
    'use_adaptive_units_tt':
        'Grove的好幾種參數都使用了單位, 其中有些表示微小距離. '
        '啟用自適應單位的情況下0.001m將被顯示為1mm.',

    'language': '語言',
    'language_tt': '用於介面和工具提示的語言',

    # New
    'grove': 'Grove',

    'label_direction': '起始方向',
    'panel_auto_prune': '自動剪枝',

    'twig_side_on_tips': '末端處的側邊',
    'twig_side_on_tips_tt':
        '在每根枝幹的末端, 末端枝葉旁還分佈有側邊枝葉. '
        '重新構建您的樹木可查看效果.',

    'rebuild': '構建',
    'rebuild_tt': '重新構建您的樹木模型的網格. 重新構建您的樹木來更新多邊形縮減, 頂點圖層, 粗細比例和側邊枝葉的分佈.',
    'add_new_grove': '添加小樹林',
    'add_new_grove_tt': '添加新的小樹林集合.',

    "select_a_grove_collection": "选择一个小树林集合",

    'select_linked_branches_tt': '將當前所選擴大到整個枝幹及其子枝幹.',
    'select_linked_branches': '選擇鏈接的枝幹',

    'show_dead_preview': '顯示死亡的',

    'twig_pick_collections': '集合',
    'twig_pick_collections_tt': '在當前檔中拾取任一枝葉對象的集合.',

    'disable_outline': '禁用輪廓',
    'disable_outline_tt':
        '為使調整時樹木能有正確的表現和更好的視覺回饋, 可點擊禁用輪廓陰影. '
        '輪廓陰影會令枝幹顯得比真實的樣子粗大了很多.',

    'set_background': '加亮背景',
    'set_background_tt':
        '點擊可加亮您的視窗背景並將其設為中等灰度. '
        '將能非常容易地見到樹木的枝幹, 您的樹木也會有更好的觀感.',

    'bend_twig_mass_solidify': '固化',
    'bend_twig_mass_solidify_tt':
        '固化枝幹末端處下拉的重量所致的彎曲. 該重量會隨著季節而變化, 沉重的春花, 大葉子還有厚實的果實全都會下拉枝幹. '
        '不過當枝幹變硬的時間到來時, 其中的大部分重量可能已經被除去了. '
        '因而此[固化]參數往往比用於固化枝幹重量的那個[固化]參數要小.',

    'add_up': '向上',
    'add_up_tt':
        '芽的反向向重力性 - 向上開始新的枝幹生長, 遠離重力. 改用負值可向下生長.',

    'regrow': '重新生長',
    'regrow_tt': '重新開始並快速將樹木重新生長至當前年齡 - 不僅跳過構建步驟, 連剪枝您的樹木的機會也略過.',

    'twig_hide': '',
    'twig_hide_tt': '暫時隱藏枝葉可完整瞭解分枝結構.',

    'twig_longevity': '生命',
    'twig_longevity_tt':
        '在每根枝幹的末端附近複製出生長年齡較短的側邊枝葉. '
        '增大此參數可使枝葉越來越多的出現在生長年齡較長較粗大的枝幹段節上. '
        '需要重新構建才能顯示.',

    'replant_grove': '重新種植',
    'replant_grove_tt': '重新種植.',

    'manual_bend': '彎曲',
    'manual_bend_tt':
        '指靈感來自用金屬線彎曲枝幹這種盆栽技法的工具, 但是其更加靈活, '
        '哪怕最粗大的枝幹都能夠將其彎曲, 即使生長完全的樹木也能夠對其塑形.',

    'label_animating_wind': '正在為風設置動畫...',
    'label_stop': '停止',

    'twig_object_upward': '上長',
    'twig_object_upward_tt':
        '指一種可選的枝葉模型, 當其向上急劇生長時會覆蓋末端枝葉. '
        '這些枝葉往往更長一些, 並且會令自身的葉子在各個方向上都盤繞扭轉. '
        '如果未設置枝葉, 則會改為使用末端枝葉.',

    'twig_object_dead': '死亡',
    'twig_object_dead_tt':
        '指一種可選的枝葉模型, 如果該模型為枯葉則會覆蓋所有其他類型的枝葉. '
        '如果未設置枝葉, 則不會有枝葉用於枯葉, 這將導致低強度區域的細節丟失.',

    'import_preset': '導入種子檔...',
    'import_preset_tt': '存儲在.seed.json檔中的預設, 您可以將其與他人分享 - 導入這一檔即可將預設添加到您的預設列表.',

    'placeholder_delay': '延緩',
    'placeholder_delay_tt': '指開始生長之前等待的年數.',

    'panel_build_base': '基部',

    'twig_wither': '枯萎',
    'twig_wither_tt':
        '指枯葉在樹木上停留加枯萎的年數(死去後).\n'
        '重新構建可查看效果.',

    'add_tree': '種植',
    'add_tree_tt':
        '添加空對象來從其處進行生長. '
        '移動, 旋轉, 複製或刪除此類對象來生長成群的樹木, 每一棵樹木都擁有各自的位置和角度.',

    'save_preferences': '保存首選項',
    'save_preferences_tt': '保存您的首選項來記住這一設置.',

    'old_release_warning_line_1': '樹木是在舊發佈版本中生長的.',
    'old_release_warning_line_2': '改動的地方非常多.',
    'old_release_warning_line_3': '請使用舊發佈版本編輯.',

    'thicken_deadwood': '枯木',
    'thicken_deadwood_tt':
        '墜落的或被剪枝的枝幹會留下一塊兒樹木做了部分修復的缺口. '
        '但核心的一小部分會死亡, 新的生長則將由樹木通過增加更多的厚度這種方式來進行補償. '
        '這樣一來, 隨著時間的推移就會為軀幹增加更多的厚度.',


    'grow_together': '一起生長',
    'grow_together_tt':
        '將所有獨立的小樹林集合作為一個來一起生長, 以便您能混合不同的樹種.'
        '通過將陰影和向光性的計算相結合, 可使這些小樹林爭奪光照.',

    'draw': '繪製',
    'draw_tt': '繪製新的枝幹. 其會逐年生長, 直至整個路徑得到了遵從.',

    'prune_status_draw_lines': '繪製',


    # Manual bend
    'bend_tool_distance': '距離',
    'bend_tool_distance_tt': '',

    'bend_tool_bend_button': '彎曲',
    'bend_tool_bend_button_tt': '空格鍵',

    'close_button': '',
    'close_button_tt': '關閉',

    'turntable': '',
    'turntable_tt': '視圖',

    'bend_tool_curve': '彎曲線',
    'bend_tool_curve_tt': '彎曲的形狀',
    'bend_tool_curve_simple': '簡單',
    'bend_tool_curve_flexible': '靈活',
    'bend_tool_curve_s_curve': 'S型彎曲線',


    # Wind
    'wind_vector': '風',
    'wind_vector_tt': '速度和方向',
    'wind_turbulence': '擾動',
    'wind_turbulence_tt': '使枝葉飛起, 令枝幹在風中起舞.',

    'wind_shapes': '形狀關鍵幀',
    'wind_shapes_tt':
        '每個形狀相隔2個關鍵幀並會連貫插值\n'
        '風會自動迴圈',


    # Record
    'record_enabled': '錄製',
    'record_enabled_tt':
        '將生長作為一系列對象錄製到名為[錄製]的專用集合中. '
        '為了做到短時可見, 每個步驟都設置有關鍵幀. 序列中的所有這些對象構成了您的生長動畫.',

    'record_start': '起始幀',
    'record_start_tt': '在此幀處開始的時間內向前移位動畫.',

    'record_interval': '間隔',
    'record_interval_tt':
        '每一年是一種連貫插值, 從樹木初始的春季形狀, 到其生長完全的夏季形狀. '
        '可為這種插值定義幀數 - 接著就有了生長速度. '
        '您可以隨時調整此值, 您的動畫也會被瞬間更新.',

    'grow_tool_growing': '正在生長',
    'grow_tool_growing_tt': '按Esc鍵可取消.',
    'grow_tool_building': '正在構建網格',

    'placeholder': '占位符',


    # Surround
    "surround_enabled": "環繞",
    "surround_enabled_tt":
    "用阻擋四面光線的牆圍住樹木。"
    "樹木會長得更高並丟失下部樹枝。"
    "無需種植整片森林，即可培養森林樹木。",

    "surround_density": "密度",
    "surround_density_tt":
    "在開闊的田野或密集的森林之間成長，或介於兩者之間。",

    "surround_height": "高度",
    "surround_height_tt":
    "用於成熟樹木或建築物的固定高度。"
    "使用自動高度讓周圍環境跟隨樹木生長。",

    "surround_grow": "生長",
    "surround_grow_tt":
    "每年自動增加高度 - 周圍的樹木與您的樹木一起生長。",

    "surround_distance": "距離",
    "surround_distance_tt": "生長的空間。",

    "auto_prune_dangling": "懸垂",
    "auto_prune_dangling_tt":
        "在自動修剪高度剛好以上的樹枝會向兩側生長並隨著質量的增加向下彎曲。"
        "像垂柳一樣讓這些懸垂的樹枝生長，或者將它們修剪到設定的高度。",

    "stake_enabled": "支撐",
    "stake_enabled_tt": "支撐樹幹，使其直立生長。",

    "stake_height": "高度",
    "stake_height_tt": "支撐樹木至此高度，使樹幹直立生長。",


    # Plant
    "plant": "種植",
    "plant_tt":
        "種植一群樹木 - 創建果園、樹籬或天然樹島。"
        "此工具可創建空對象，您可以自由移動、複製或刪除。",

    "plant_layout": "佈局",
    "plant_layout_tt": "種植果園、種植園、樹籬、環形或天然樹叢",

    "plant_trees": "樹木",
    "plant_trees_tt": "樹木數量",

    "plant_space": "空間",
    "plant_space_tt": "樹木之間的距離",

    "plant_random_shift": "隨機偏移",
    "plant_random_shift_tt": "不規則放置",
    "plant_random_seed": "隨機種子",
    "plant_random_seed_tt": "改變隨機偏移",
    "plant_delay": "延遲",
    "plant_delay_tt": "距離中心較遠的樹木在較晚的年份開始生長。",
    "plant_ring_radius": "半徑",
    "plant_ring_radius_tt": "與中心環的距離",
    "plant_rows_trees_tt": "每行樹木數量",
    "plant_rows": "行",
    "plant_rows_tt": "行數",
    "plant_rows_space": "間距",
    "plant_rows_space_tt": "行之間的空間",
    "plant_rows_diagonal": "對角",
    "plant_rows_diagonal_tt": "將每個第二行移動以獲得菱形圖案",
    "plant_islands_trees_tt": "每個島上的樹木平均數量",
    "plant_islands": "島嶼",
    "plant_islands_tt": "樹島數量",
    "plant_islands_space": "島嶼空間",
    "plant_islands_space_tt": "樹島之間的平均距離",
    "plant_islands_clearing": "空地",
    "plant_islands_clearing_tt": "中間的開放空地",
    "plant_islands_randomize": "隨機",
    "plant_islands_randomize_tt": "改變每個島上的樹木數量",
    "plant_layout_clump": "叢",
    "plant_layout_rows": "行",
    "plant_layout_ring": "環",
    "plant_layout_islands": "島",
    "plant_variation_panel": "變化",
    "plant_diverge": "偏離",
    "plant_diverge_tt": "遠離附近的樹木。",
    "plant_terrain_panel": "地形",
    "plant_terrain_drop": "投影",
    "plant_terrain_drop_tt": "將樹木投影到地面。",
    "plant_terrain_slope": "坡度",
    "plant_terrain_slope_tt": "在旋轉中考慮景觀的坡度。",
    "escape_to_stop": "按Esc鍵停止",

    "restart_all": "重新開始所有",
    "restart_all_tt": "重新開始每個樹叢集合。",

    "wind_breeze": "微風",
    "wind_breeze_tt":
        "用生動的微風動畫為小樹枝注入生命。"
        "您可以將其與常規風動畫結合使用以產生更強的變形。",

    "widget_scale": "控件縮放",
    "widget_scale_tt":
        "如果螢幕上的徑向UI控件過小或過大, 請調整它們的大小.",


    # File tool
    'file': "檔案",
    "file_tt": "存儲供以後使用的樹木，或在應用程序之間傳輸樹木。",

    "file_recent": "最近",

    "file_import": "導入樹木",
    "file_import_tt": "從 .grove 文件導入模擬。",

    "file_export": "導出樹木",
    "file_export_tt": "將當前模擬導出到 .grove 文件。",


    # Roots
    "roots": "根",
    "roots_tt": "生成地表根。根通常在地下生長，但可能因土壤侵蝕而暴露。地表根在視覺上令人愉悅，將樹木固定在地面上。",

    "roots_roots_panel": "根",
    "roots_number": "數量",
    "roots_number_tt": "主根的數量",
    "roots_nodes": "節點",
    "roots_nodes_tt": "每根主根的節點數",
    "roots_length": "長度",
    "roots_length_tt": "兩個節點之間的長度。",
    "roots_climb": "攀升",
    "roots_climb_tt": "使根沿著樹幹向上生長，形成平滑過渡。",
    "roots_turn_down": "向下生長",
    "roots_turn_down_tt": "",

    "roots_branches_panel": "側根",
    "roots_branches_panel_tt": "",
    "roots_generations": "代",
    "roots_generations_tt": "添加更多代以更詳細地展開根系。",
    "roots_density": "密度",
    "roots_density_tt":
        "生長側根的機會。要進一步增加密度，增加節點數並減小節間長度。",
    "roots_add_angle": "角度",
    "roots_add_angle_tt": "與主根的夾角。",
    "roots_add_down": "向下添加",
    "roots_add_down_tt": "",

    "roots_variation_panel": "隨機",
    "roots_random_heading": "方向",
    "roots_random_heading_tt": "在地面上爬行。",
    "roots_random_pitch": "俯仰",
    "roots_random_pitch_tt": "在生長過程中向上和向下轉動。",
    "roots_random_seed": "種子",
    "roots_random_seed_tt": "",

    "roots_thickness_panel": "厚度",
    "roots_thickness": "厚度",
    "roots_thickness_tt": "主根的平均厚度。",
    "roots_thickness_reduce": "減少",
    "roots_thickness_reduce_tt": "",
    "roots_thickness_random": "隨機",
    "roots_thickness_random_tt": "",

    "roots_terrain_panel": "地形",
    "roots_terrain_panel_tt": "",
    "roots_drop": "下落",
    "roots_drop_tt": "",

    "restart_single_tree": "單棵樹",
    "restart_single_tree_tt": "移除佔位符並在原點種植一棵樹。",

    "restart_revert": "重新開始",
    "restart_revert_tt": "將所有內容重置為默認值，重新加載當前預設並從一棵樹開始.",

    'shade_avoidance': '陰影促進',  # Escape Shade
    'shade_avoidance_tt':
        '增大或減小被遮光枝幹處的[偏重末端]. '
        '作為一種尋找光照的策略, 每根枝幹都控制著其自身的[偏重末端]. '
        '枝幹被遮光的越多, 其為了擺脫陰影也就越偏重自身的末端生長, '
        '或者其為了吸收盡可能多的微光也就越偏重側邊生長. '
        '您可在森林地表樹種, 如山毛櫸和榛樹中見到後一種情況.',

    'shade_sensitivity': '敏感度',
    'shade_sensitivity_tt':
        '指對陰影的靈敏度. '
        '陰影是從亮到暗的線性值, 不過大自然中的過程經常會以一種指數方式回應. '
        '將0設為對陰影的慢回應, 這樣枝幹就只會在其收到了相當多的陰影之後才反應. '
        '將1設為即時反應, 這樣一丁點兒的陰影都會被不成比例地放大.',

    'shade_elongation': '陰影處更長',
    'shade_elongation_tt':
        '被遮光的枝幹生長的有長有短. '
        '陰影中生長的植物希望尋找光照, 所以會生長的更長一些. '
        '此參數加之粗細上的減小, 就會創造出較長但又較弱的, 彎曲很厲害的枝幹來. '
        '此參數可以創出經常能在冠部的底部見到的那樣的懸掛枝幹來.',

    'label_layers': '圖層',

    'branching_inefficiency': '效率低',
    'branching_inefficiency_tt':
        '這是限制子枝幹還有它們接連的子枝幹的生長強度的直接方式. '
        '枝幹的附屬部分有缺陷, 因而會限制水分運輸.',

    'sapwood': '邊材',
    'sapwood_tt':
        '指活木的粗細. 邊材是運輸水分的一類活木.'
        '枝幹的核心內部是枯木, 其只充當著支撐結構, 被稱為心材.'
        '增加此值就會在粗枝幹上形成較少的厚度累積.',
    
    "sow_enabled": "播種",
    "sow_enabled_tt": "在現有老樹周圍散播種子，模擬自然擴展的樹林。",
    
    "sow_age": "延遲",
    "sow_age_tt": "樹木需要幾年時間生根並建立能量正平衡狀態，然後才開始產生種子。",
    
    "sow_chance": "概率",
    "sow_chance_tt":
        "每年每棵樹創造成功後代的概率。"
        "實際上，某些樹木每年可能產生數千顆種子，其中數百顆可能發芽。"
        "但幾乎沒有一顆能存活並長成適當的樹木。"
        "為了保持模擬以可用的速度運行，請保持較低的概率。",
    
    "sow_distance": "距離",
    "sow_distance_tt": "種子在現有樹木周圍的一定距離內散播。",
    
    "sow_limit": "限制",
    "sow_limit_tt": "最大樹木數量。超過此數量後停止添加新樹，以保持模擬平穩運行。",
}
