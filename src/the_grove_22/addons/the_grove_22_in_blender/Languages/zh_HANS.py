# coding=utf-8

dictionary = {

    '': '',

    # Panel titles
    'panel_presets': '预设',
    'panel_simulation': '模拟',
    'panel_favor': '偏重',
    'panel_drop': '坠落',
    'panel_add': '增添',
    'panel_grow': '生长',
    'panel_turn': '转动',
    'panel_react': '反应',
    'panel_thicken': '变粗',
    'panel_bend': '弯曲',
    'panel_shade': '遮光',
    'panel_build': '构建',
    'panel_build_texture': '纹理',
    'panel_build_wind': '风',
    'panel_twigs': '拾取枝叶',


    # User preferences
    'set_twigs_path': '设置枝叶文件夹...',
    'twigs_path': '枝叶文件夹',
    'twigs_path_tt': '指向您将枝叶存储其中的文件夹. 这些枝叶会被罗列在枝叶拾取器中.',
    'set_textures_path': '设置纹理文件夹...',
    'textures_path': '树皮纹理文件夹',
    'textures_path_tt': '指向您将树皮纹理存储其中的文件夹. 这些纹理会被罗列在纹理拾取器中.',


    # Interface messages
    'remove_preset_info': '要移除{}吗?',
    'overwrite_preset_info': '要覆盖{}吗?',
    'name_preset_info': '命名您的预设.',
    'height_info': '{:.1f}米',
    'age_info': '{}年',
    'branch_info': '{}根枝干',
    'branches_info': '{:,}根枝干',
    'polygons_info': '{:,}个面',
    'tips_info': '请阅读工具提示:',

    "tweak": "调整",
    "tweak_tt": "在视图中对这些参数进行调整，并显示可视化的变化.",


    # Presets
    'presets_menu': '',  # Read
    'presets_menu_tt': '加载树种的预设参数',

    'preset_name': '新名称',
    'preset_name_tt': '指保存或覆盖的预设名称',

    'remove_preset': '移除',
    'remove_preset_tt': '移除此预设',

    'cancel_action': '取消',

    'remove_preset_confirm': '移除',
    'remove_preset_confirm_tt': '确认移除此预设',

    'rename_preset': '重命名',
    'rename_preset_tt': '重命名此预设',

    'add_preset': '添加',
    'add_preset_tt': '添加一种新预设, 或是在某一预设名称已存在的情况下替换该预设.',

    'overwrite_preset': '覆盖',
    'overwrite_preset_tt': '覆盖此预设',

    'overwrite_preset_confirm': '覆盖',
    'overwrite_preset_confirm_tt': '确认替换此预设',

    'save_preset': '保存',
    'save_preset_tt': '将当前属性保存为预设',


    # Simulate
    'simulation_flushes': '年轮',
    'simulation_flushes_tt':
        '新增应生长年数. '
        '采用小的交互步骤模拟您的树木. '
        '每一步之后您都可以通过剪枝操作来操纵您的树木, '
        '甚至可能还会用到调整树木参数, 或是改变其生长所处的环境.',

    'zoom': '缩放',
    'zoom_tt': '进行缩放为的是在视窗中适配整个树木',

    'simulate': '生长',
    'simulate_tt':
        '生长您的树木. '
        '通过采用交互步骤生长, 转动, 弯曲, 流动和剪枝来模拟四季. '
        '观看您的树木一年又一年的成长.',

    'restart': '重新开始',
    'restart_tt':
        '移除树木并重新开始. '
        '调整您的树木的树体特征经常是一个反复试验的过程. '
        '即使您的设置全都完全正确时, 大自然又会不够完美. '
        '生长, 调整, 重新开始, 重复..., 这就是生长树木的方式.',

    'manual_prune': '剪枝',
    'manual_prune_tt':
        '在视窗中绘制出切割线可移除或缩短枝干.',

    # Flow
    'favor_end': '末端',
    'favor_end_tt':
        '[偏重末端]给予枝干末端的是完全覆盖新侧枝的[头部开始]. '
        '[头部开始]会创造出先从其开始的较为短小, 强度不大的侧边枝叶来, 不过[头部开始]并不一定是稳赢的一方. '
        '[偏重光亮]接替, 会慢慢转变于最佳表现群体有利的胜算 - '
        '目的是使短小的侧边枝叶能够赶上来甚至是作为新的主导枝干来接替. '
        '[偏重光亮]和[偏重末端]是最为重要的树体特征中的两个. '
        '它们共同发挥着作用, 可创造出广泛的形状和树体特征.',

    'shade_avoidance': '阴影促进',  # Escape Shade
    'shade_avoidance_tt':
        '增大或减小被遮光枝干处的[偏重末端]. '
        '作为一种寻找光照的策略, 每根枝干都控制着其自身的[偏重末端]. '
        '枝干被遮光的越多, 其为了摆脱阴影也就越偏重自身的末端生长, '
        '或者其为了吸收尽可能多的微光也就越偏重侧边生长. '
        '您可在森林地表树种, 如山毛榉和榛树中见到后一种情况.',

    'favor_bright': '光亮',
    'favor_bright_tt':
        '将树木的枝叶想象成无数的个体植物. '
        '光亮变大, 黑暗消失 - 这是最完全状态的[偏重光亮]. '
        '现在将这些植物与枝干相连 - 为的是赋予它们一种分享自身获益的方式. '
        '当糖分能自由流动且光照充足时, 哪怕被遮光的植物也将能够获得自身生长和寻找新光照所需的供养.',

    # Drop
    'auto_prune_low': '低的',
    'auto_prune_low_tt':
        '修剪低于此高度的低悬枝干. '
        '自动剪枝城市用树的基部以便允许行人和交通自由通行. '
        '坠落地面霜损毁的低悬枝干. 或是坠落被觅食动物夺走了的枝干. '
        '当树木生长的较高时此剪枝操作会逐渐开始生效.',

    'auto_prune_keep_thick': '保留粗大的',
    'auto_prune_keep_thick_tt':
        '只剪枝较细小的枝干而保留较粗大的枝干. '
        '此参数将允许树木生长出若干根大的主枝干, 从而为您的树木赋予更自然的观感. '
        '一种园艺工作者在剪枝拥有更多空间的树木时所追求的观感, 比如公园中的. '
        '这种现象也发生在自然界, 觅食的动物瞧不上粗大的枝干, 而是更为喜欢新鲜多汁的枝干.',

    "auto_prune_dangling": "悬挂",
    "auto_prune_dangling_tt":
        "处于自动修剪高度正上方的树枝会继续向侧面生长，并随着质量的增加而弯曲下垂."
        "这些悬挂的树枝可以像垂柳那样继续生长，或者您可以将它们修剪至设定的高度.",


    # Drop
    'drop_shaded': '被遮光嫩枝',
    'drop_shaded_tt':
        '坠落被遮光的枝干. '
        '每年树木都会在各个方向上生长出数不尽的新枝叶来. '
        '这些敏感的小枝干会探索新空间和寻找光照. '
        '然后树木就会将其能量只投入进光亮的枝叶中, 同时还将坠落许多被遮光的枝叶. '
        '减小此参数可保留更多枝干, 然后生长出浓密的树木来. '
        '将此参数向1增加可坠落更为光亮的枝干, 然后生长出透亮散开的树木来.',

    'drop_decay': '暂时存留',
    'drop_decay_tt':
        '将死亡的枝干留在树上. '
        '死亡的枝干腐烂并从树上脱落需要一些时间.'
        '尤其针叶树较低的躯干, 全都布满了死亡的枝干.',

    'drop_weak': '低强度末端',
    'drop_weak_tt':
        '指低于枝干末端结出花朵并停止长度上的生长的生长强度. '
        '高强度的枝干在这里用来使树木生长到新的高度. '
        '较低强度的枝干末端被赋予了结出花朵和果实的新用途. '
        '此参数会结束枝干在长度上的生长, 从而允许侧枝来接替. '
        '较高的值会增加开花的几率. ',

    # Add
    "add_side_branches": "芽",
    "add_side_branches_tt":
        "每个节点的芽数直接影响分支的几何排列，其中交替、对生"
        "和轮生模式分别对应一个、两个和三到六个芽。"
        "生长活力与机会共同决定这些芽中有多少会实际发展成新的分支。",

    'add_chance': '几率',
    'add_chance_tt':
        '指年短节点产生新枝干的几率. '
        '并不是所有的芽都会开放并生长出新枝干. '
        '有一些被霜冻或昆虫毁坏了, 还有一些被[偏重主流]抑制了.',

    'add_bud_life': '芽寿命',
    'add_bud_life_tt':
        '对大部分树种而言, 芽只会存活几年. '
        '达到此年龄的芽是能够生长出新枝叶的.'
        '而对于另外的树种而言, 几乎每一个芽都会开放, 并且基本上都会结出非常短小的, 受顶端优势限制的枝叶来. '
        '这些枝叶中的大部分会很快死去, 而其中的少数枝叶则会摆脱抑制, 生长成新的枝干.',

    'add_only_on_end': '仅在末端上',
    'add_only_on_end_tt':
        '只为末端节点添加新枝干. '
        '像针叶树这类树木会抑制激素的侧向生长. '
        '实际上这意味着只有那些非常靠近末端的节点才没有激素, 也才能够结出新枝干来.',

    'add_fork': '分叉',
    'add_fork_tt':
        '当某一枝干十分强壮且长势旺盛时, 其就能在可压制尾结的末端附近长出来若干个芽. '
        '于是枝干就会拆分成若干根强度均等的枝干. 对于中间没有主导枝干的情况, 为了将拆分成的枝干推到侧边, 分叉的枝干会按常规角度的一半来生长. '
        '分叉的树木不会形成完全单一的躯干, 而是会创造出散开型的主枝干结构来.',

    # Grow
    'grow_length': '长度',
    'grow_length_tt': '指新生长的总长度',

    'grow_nodes': '节点',
    'grow_nodes_tt':
        '枝干每年能生长的最大节点数量. 低强度的枝干会生长较少的节点.',

    'shade_elongation': '阴影处更长',
    'shade_elongation_tt':
        '被遮光的枝干生长的有长有短. '
        '阴影中生长的植物希望寻找光照, 所以会生长的更长一些. '
        '此参数加之粗细上的减小, 就会创造出较长但又较弱的, 弯曲很厉害的枝干来. '
        '此参数可以创出经常能在冠部的底部见到的那样的悬挂枝干来.',


    # Turn
    'gravitropism': '向重力',
    'gravitropism_tt':
        '向重力性. '
        '新生长的方向相对于重力的改变. '
        '负值会使枝干向上生长, 远离重力. '
        '正值会使枝干向下朝着重力生长, 从而创造出下垂的枝干来.',

    'gravitropism_shade': '被遮光时',
    'gravitropism_shade_tt':
        '完全处于阴影下的向重力性. '
        '正值会使枝干向下生长. '
        '负值会使枝干向上生长.',

    'turn_to_light': '向光',
    'turn_to_light_tt':
        '向光性. '
        '将新生长转向最光亮的方向. '
        '这是种使室内植物朝着窗户生长的效果. '
        '对于树木而言, 此效果会改善其枝干的分布.',

    'turn_to_horizon': '向地平线',
    'turn_to_horizon_tt':
        '斜向性. '
        '当枝干被遮光时将枝干的生长转向水平面.',

    'add_horizontal': '水平',
    'add_horizontal_tt':
        '芽的斜向性. '
        '叶序角朝着水平取向的转向.',

    'add_angle': '角度',
    'add_angle_tt':
        '指新枝干及其父枝干间的角度. '
        '角度范围是从枝干的直线延长线到垂直于父枝干方向的[0° - 90°]间的角.',

    'add_twist': '扭转',
    'add_twist_tt':
        '扭转每个接连的节点. '
        '像七叶树这类树种在沿着它们枝干的长度上有非常明显的扭转, '
        '您可以在躯干周围清楚地看到向上打旋儿的树皮图案. '
        '除了明显的视觉质量, 扭转还会增加芽的叶序旋转. '
        '此参数会改善相对分枝的树木上的枝干分布.',


    # Interact
    'react_block_object': '阻断',
    'react_block_object_tt':
        '与环境对象碰撞之后停止生长.',

    'react_shade_object': '阴影',
    'react_shade_object_tt':
        '环境对象会投下阴影, 从而影响那些依赖光照的参数.',

    'react_deflect_object': '偏转',
    'react_deflect_object_tt': '避开环境对象.',

    'react_attract_object': '吸引',
    'react_attract_object_tt':
        '朝着环境对象生长. '
        '枝干能穿过对象自由生长.',

    'react_vigor_object': '强度',
    'react_vigor_object_tt':
        '选择一种能控制新生长的活力的对象.',

    "react_force": "力量",
    "react_force_tt":
        "物体对树木施加的力量大小.",

    "react_falloff": "衰减",
    "react_falloff_tt":
        "效果在物体附近更强，在物体距离上呈指数衰减.",


    # Thicken
    'thicken_tips': '末梢',
    'thicken_tips_tt':
        '指枝干末端的直径. '
        '这是枝干具有满强度时的末梢粗细. '
        '较低强度的枝干可以拥有减小了的粗细.',

    'thicken_tips_reduce': '减小',
    'thicken_tips_reduce_tt':
        '减小低强度枝干处的末梢的粗细. '
        '低强度的枝干生长的会更细小. '
        '此参数会影响树木的形状, 原因是细枝干会弯曲的很厉害. '
        '尤其会影响大量抑制其侧枝的下垂针叶树的形状.',

    'thicken_join': '连接枝干',  # Grow or Merge or Join or Reinforce
    'thicken_join_tt':
        '生长的更为粗大. '
        '粗细是从尖梢开始被增加的. '
        '每当两个枝干连接时, 两者的交叉部分都会相加, 为的是创造出更粗壮的枝干来. '
        '这种行为会一路持续到树木的基部. '
        '改变枝干在粗细上的生长速度将会明显改变您的树木的形状. '
        '增加了的粗细会强化枝干并减少弯曲.',

    'thicken_base_scale': '基部比例',
    'thicken_base_scale_tt':
        '增加基部处的粗细. '
        '在躯干的根部, 增加根部生长所造成的粗细.',

    'thicken_base_shape': '形状',
    'thicken_base_shape_tt':
        '调整[根比例]缓慢融入躯干的形状.',

    'thicken_base_buttress': '根突',
    'thicken_base_buttress_tt':
        '指带有根突体的多样[根比例].',

    'root_distribution': '分布',
    'root_distribution_tt':
        '指遍布躯干之上的[根比例]效应的到达率.',


    # Bend
    'bend_mass': '枝干弯曲量',
    'bend_mass_tt':
        '指迫于枝干重量而弯曲的效果量. '
        '枝干的弯曲会对树木的形状造成巨大影响, 特别是长成年长枝干的情况下更是如此. '
        '枝干会弯曲多少取决于自身的粗细 - '
        '较粗大的枝干重量就越大, 不过在对抗重力方面, 增加的交叉部分能令它们以指数形式变得更为强壮.',

    'bend_twig_mass': '枝干末端弯曲量',
    'bend_twig_mass_tt':
        '指迫于叶子重量而弯曲的效果量. '
        '枝干末端会承载相对较重的重量, 这些重量来自它们那些长满叶子, 花朵和果实的枝叶. '
        '树木会借助反向向重力性通过向上生长来尽量反抗此弯曲. '
        '弯曲和向重力性间的相互影响对于帚状树体特征或垂枝型树体特征的形成都发挥着重要作用.',

    'bend_reaction': '反应',
    'bend_reaction_tt':
        '反应木材会令长势强劲的枝干随着时间的推移主动向后弯曲.',


    # Shade
    'shade_area': '叶面积',
    'shade_area_tt':
        '指每个枝干末端处的阴影投射面积, 以dm²为单位. '
        '值为4.0的[叶面积]等于值为10cm x 10cm的面积的4倍. '
        '请注意, 这是枝叶的复合叶面积, 不是单个叶子的面积.',

    'shade_sensitivity': '敏感度',
    'shade_sensitivity_tt':
        '指对阴影的灵敏度. '
        '阴影是从亮到暗的线性值, 不过大自然中的过程经常会以一种指数方式响应. '
        '将0设为对阴影的慢响应, 这样枝干就只会在其收到了相当多的阴影之后才反应. '
        '将1设为即时反应, 这样一丁点儿的阴影都会被不成比例地放大.',


    # Build

    'build_resolution': '分辨率',
    'build_resolution_tt':
        '指树木的基部(位于其最粗大的部位)处的顶点数量.',

    'build_resolution_reduce': '缩减',
    'build_resolution_reduce_tt':
        '缩减较细小枝干处的多边形. '
        '树木的大部分多边形都位于其无数的年短枝干里. '
        '在不损失视觉质量的情况下这些细枝干可以使用较少的多边形.',


    'smooth': '平滑',
    'smooth_tt':
        '减小尖角的角度可创建更为平滑弯曲的枝干.',

    'texture_bark': '树皮纹理',
    'texture_bark_tt':
        '拾取纹理',

    'texture_repeat': 'UV重复',
    'texture_repeat_tt':
        '指围绕树木基部的周长重复树皮纹理的次数 - '
        '在较细小的枝干处就自动减少了.',

    'simulation_scale':
        '按比例缩放',
    'simulation_scale_tt':
        '使预设适应不同的枝叶大小. '
        '一个普通的枝叶包含1年或2年的生长, 有大约30cm长. '
        '预设被设计用来匹配此大小. 不过枝叶模型可以是您想要的任意大小, 从单叶一直到有数年生长的都可以. '
        '匹配不同大小的枝叶的方式就是简单地按比例放大或缩小枝干模型. '
        '此操作会按同一真实比例保留您的枝叶.',

    'twig_menu': '枝叶',  # Twigs, Library, Pick
    'twig_menu_tt':
        '拾取一组枝叶以便将它们添加到您的树木上. '
        '此菜单列举出了能在枝叶文件夹中找到的每一种枝叶 - '
        '您可以在Grove的用户首选项中选择文件夹. '
        '或者还可以从当前场景拾取对象.',

    'twig_pick_objects': '场景对象',
    'twig_pick_objects_tt': '拾取场景中的任意3D对象.',

    'twig_no_twigs': '无枝叶',
    'twig_no_twigs_tt': '没有枝叶',

    'calculate_wind': '设置动画',
    'calculate_wind_tt': '为您的树木添加风动画.',

    'twig_object_end': '末端',
    'twig_object_end_tt':
        '指在枝干末端处分布的枝叶对象. '
        '末端枝叶是指带有叶子, 有时是花朵和后结果实的全新生长. '
        '末端枝叶是现有枝干的延伸 - 往往比侧边枝叶要强壮的多, 长的多.',

    'twig_object_side': '侧边',
    'twig_object_side_tt':
        '指沿着枝干的侧边分布的枝叶对象. '
        '侧边枝叶是指沿现有枝干的侧边长出来的全新枝干. '
        '它们携带有叶子, 有时是花朵和后结果实. '
        '侧边枝叶往往比末端枝叶要短, 这是产生它们的主导枝干存在激素抑制所致.'
        '最终只有最强壮的枝叶才会长成全新的枝干.',

    'twig_density': '密度',
    'twig_density_tt':
        '通过添加或多或少的侧边枝叶来控制您树木的树叶密度.',

    'twig_view_detail': '视图细节',
    'twig_view_detail_tt':
        '降低枝叶的显示分辨率. '
        '为了获得更好的视窗性能, 此参数会为每个枝叶模型都添加[精简]修改器. '
        '视窗会使用修改了的低分辨率模型 - 针对渲染引擎使用原始模型的情况.',

    'use_adaptive_units': '使用自适应单位',
    'use_adaptive_units_tt':
        'Grove的好几种参数都使用了单位, 其中有些表示微小距离. '
        '启用自适应单位的情况下0.001m将被显示为1mm.',

    'language': '语言',
    'language_tt': '用于界面和工具提示的语言',

    'favor_rising': '上升',
    'favor_rising_tt':
        '对向上生长枝干的偏重超过了那些垂下来的枝干. '
        '向上促进枝干可获得高耸的树木. '
        '值为1时会尽可能地将水平枝干的强度降低至零.',

    # New
    'grove': 'Grove',

    'label_direction': '起始方向',
    'panel_auto_prune': '自动剪枝',

    'label_layers': '图层',

    'branching_inefficiency': '效率低',
    'branching_inefficiency_tt':
        '这是限制子枝干还有它们接连的子枝干的生长强度的直接方式. '
        '枝干的附属部分有缺陷, 因而会限制水分运输.',

    'sapwood': '边材',
    'sapwood_tt':
        '指活木的粗细. 边材是运输水分的一类活木.'
        '枝干的核心内部是枯木, 其只充当着支撑结构, 被称为心材.'
        '增加此值就会在粗枝干上形成较少的厚度累积.',

    'twig_side_on_tips': '末端处的侧边',
    'twig_side_on_tips_tt':
        '在每根枝干的末端, 末端枝叶旁还分布有侧边枝叶. '
        '重新构建您的树木可查看效果.',

    'rebuild': '构建',
    'rebuild_tt': '重新构建您的树木模型的网格. 重新构建您的树木来更新多边形缩减, 顶点图层, 粗细比例和侧边枝叶的分布.',
    'add_new_grove': '添加小树林',
    'add_new_grove_tt': '添加新的小树林集合.',

    "select_a_grove_collection": "选择树丛收藏",

    'select_linked_branches_tt': '将当前所选扩大到整个枝干及其子枝干.',
    'select_linked_branches': '选择链接的枝干',

    'show_dead_preview': '显示死亡的',

    'twig_pick_collections': '集合',
    'twig_pick_collections_tt': '在当前文件中拾取任一枝叶对象的集合.',

    'disable_outline': '禁用轮廓',
    'disable_outline_tt':
        '为使调整时树木能有正确的表现和更好的视觉反馈, 可点击禁用轮廓阴影. '
        '轮廓阴影会令枝干显得比真实的样子粗大了很多.',

    'set_background': '加亮背景',
    'set_background_tt':
        '点击可加亮您的视窗背景并将其设为中等灰度. '
        '将能非常容易地见到树木的枝干, 您的树木也会有更好的观感.',

    'bend_twig_mass_solidify': '固化',
    'bend_twig_mass_solidify_tt':
        '固化枝干末端处下拉的重量所致的弯曲. 该重量会随着季节而变化, 沉重的春花, 大叶子还有厚实的果实全都会下拉枝干. '
        '不过当枝干变硬的时间到来时, 其中的大部分重量可能已经被除去了. '
        '因而此[固化]参数往往比用于固化枝干重量的那个[固化]参数要小.',

    'turn_up': '向上',
    'turn_up_tt': '反向向重力性. 将新的生长转为向上, 远离重力. 改用负值可向下生长.',

    'turn_up_in_shade': '阴影处向上',
    'turn_up_in_shade_tt': '将被遮光的生长转为向上, 远离重力. 改用负值可向下生长.',

    'add_up': '向上',
    'add_up_tt':
        '芽的反向向重力性 - 向上开始新的枝干生长, 远离重力. 改用负值可向下生长.',

    'regrow': '重新生长',
    'regrow_tt': '重新开始并快速将树木重新生长至当前年龄 - 不仅跳过构建步骤, 连剪枝您的树木的机会也略过.',

    'twig_hide': '',
    'twig_hide_tt': '暂时隐藏枝叶可完整了解分枝结构.',

    'twig_longevity': '生命',
    'twig_longevity_tt':
        '在每根枝干的末端附近复制出生长年龄较短的侧边枝叶. '
        '增大此参数可使枝叶越来越多的出现在生长年龄较长较粗大的枝干段节上. '
        '需要重新构建才能显示.',

    'replant_grove': '重新种植',
    'replant_grove_tt': '重新种植.',

    'attribute_age': '年龄',

    'manual_bend': '弯曲',
    'manual_bend_tt':
        '指灵感来自用金属线弯曲枝干这种盆栽技法的工具, 但是其更加灵活, '
        '哪怕最粗大的枝干都能够将其弯曲, 即使生长完全的树木也能够对其塑形.',

    'label_animating_wind': '正在为风设置动画...',
    'label_stop': '停止',

    'twig_object_upward': '上长',
    'twig_object_upward_tt':
        '指一种可选的枝叶模型, 当其向上急剧生长时会覆盖末端枝叶. '
        '这些枝叶往往更长一些, 并且会令自身的叶子在各个方向上都盘绕扭转. '
        '如果未设置枝叶, 则会改为使用末端枝叶.',

    'twig_object_dead': '死亡',
    'twig_object_dead_tt':
        '指一种可选的枝叶模型, 如果该模型为枯叶则会覆盖所有其它类型的枝叶. '
        '如果未设置枝叶, 则不会有枝叶用于枯叶, 这将导致低强度区域的细节丢失.',

    'import_preset': '导入种子文件...',
    'import_preset_tt': '存储在.seed.json文件中的预设, 您可以将其与他人分享 - 导入这一文件即可将预设添加到您的预设列表.',

    'placeholder_delay': '延缓',
    'placeholder_delay_tt': '指开始生长之前等待的年数.',

    'panel_build_base': '基部',

    'attribute_twig_upward': '上长枝叶',

    'attribute_twig_dead': '枯叶',

    'twig_wither': '枯萎',
    'twig_wither_tt': '指枯叶在树木上停留加枯萎的年数(死去后).\n'
                           '重新构建可查看效果.',

    'add_tree': '种植',
    'add_tree_tt': '添加空对象来从其处进行生长. '
                   '移动, 旋转, 复制或删除此类对象来生长成群的树木, 每一棵树木都拥有各自的位置和角度.',

    'save_preferences': '保存首选项',
    'save_preferences_tt': '保存您的首选项来记住这一设置.',

    'old_release_warning_line_1': '树木是在旧发布版本中生长的.',
    'old_release_warning_line_2': '改动的地方非常多.',
    'old_release_warning_line_3': '请使用旧发布版本编辑.',

    'thicken_deadwood': '枯木',
    'thicken_deadwood_tt':
        '坠落的或被剪枝的枝干会留下一块儿树木做了部分修复的缺口. '
        '但核心的一小部分会死亡, 新的生长则将由树木通过增加更多的厚度这种方式来进行补偿. '
        '这样一来, 随着时间的推移就会为躯干增加更多的厚度.',

    'shade_area_depth': '深度',
    'shade_area_depth_tt':
        '上提阴影投射器的侧边可增大形状的深度. '
        '这样做会致使树木的侧边投射出较多的阴影, 整体的阴影也会因此而变多. '
        '您可以通过减少下落遮光的方式进行补偿. '
        '启用阴影预览可查看效果.',

    'grow_together': '一起生长',
    'grow_together_tt':
        '将所有独立的小树林集合作为一个来一起生长, 以便您能混合不同的树种.'
        '通过将阴影和向光性的计算相结合, 可使这些小树林争夺光照.',

    'shade_leaf_sides': '侧边',
    'shade_leaf_sides_tt':
        '沿枝干的侧边也会分布遮光叶面积. '
        '枝干末端处有叶子, 再加上很少一部分表现力不错的抽象概念就能模拟大部分树木. '
        '但是在那些带有垂枝型枝干的树木上是需要有侧枝的. '
        '请注意, 这种情况您需要使用较小的叶面积, 因为将会有更多的枝叶被放置.',

    'shade_area_reduce': '减少',
    'shade_area_reduce_tt': '减小较低强度的枝干上的叶面积.',

    'draw': '绘制',
    'draw_tt': '绘制新的枝干. 其会逐年生长, 直至整个路径得到了遵从.',

    'prune_status_draw_lines': '绘制',

    'bend_tool_distance': '距离',
    'bend_tool_distance_tt': '',

    'bend_tool_bend_button': '弯曲',
    'bend_tool_bend_button_tt': '空格键',

    'close_button': '',
    'close_button_tt': '关闭',

    'turntable': '',
    'turntable_tt': '视图',

    'bend_tool_curve': '弯曲线',
    'bend_tool_curve_tt': '弯曲的形状',
    'bend_tool_curve_simple': '简单',
    'bend_tool_curve_flexible': '灵活',
    'bend_tool_curve_s_curve': 'S型弯曲线',

    'wind_vector': '风',
    'wind_vector_tt': '速度和方向',
    'wind_turbulence': '扰动',
    'wind_turbulence_tt': '使枝叶飞起, 令枝干在风中起舞.',

    'wind_shapes': '形状关键帧',
    'wind_shapes_tt':
        '每个形状相隔2个关键帧并会连贯插值\n'
        '风会自动循环',

    'record_enabled': '录制',
    'record_enabled_tt':
        '将生长作为一系列对象录制到名为[录制]的专用集合中. '
        '为了做到短时可见, 每个步骤都设置有关键帧. 序列中的所有这些对象构成了您的生长动画.',

    'record_interval': '间隔',
    'record_interval_tt':
        '每一年是一种连贯插值, 从树木初始的春季形状, 到其生长完全的夏季形状. '
        '可为这种插值定义帧数 - 接着就有了生长速度. '
        '您可以随时调整此值, 您的动画也会被瞬间更新.',

    'record_start': '起始帧',
    'record_start_tt': '在此帧处开始的时间内向前移位动画.',

    'grow_tool_growing': '正在生长',
    'grow_tool_growing_tt': '按Esc键可取消.',
    'grow_tool_building': '正在构建网格',

    'drop_obsolete': '废弃',
    'drop_obsolete_tt':
        '随着树木的生长, 较低的枝干会被遮光, 小枝干也会因此而坠落. '
        '老的主枝干会比供养自身逐渐减少的树叶所需的那些枝干要粗大. '
        '此类附加木材无法得到供养, 枝干最终会废弃, 腐烂然后坠落.'
        '重度手工剪枝之后也会出现这种情况.',

    'placeholder': '占位符',

    'add_regenerate': '再生',
    'add_regenerate_tt':
        '重度剪枝或自然毁坏之后会沿着枝干附加地结出再生嫩枝来. '
        '在缺少树叶供养的情况下, 附加木材中的能量会令老的休眠芽获得二次修复树木和填补间隙的机会.'
        '针叶树种很少会结出再生嫩枝来.',

    # Surround tool
    "surround_enabled": "环绕",
    "surround_enabled_tt":
        "用阻挡四面光线的墙将树木围起来."
        "树木会长得更高，失去它们的下部树枝."
        "在不用种植整片森林的情况下，种植一棵森林树.",
    "surround_density": "密度",
    "surround_density_tt":
        "在开阔的田野、密集的森林或其他任何地方生长.",
    "surround_height": "高度",
    "surround_height_tt":
        "可用于成熟树木或建筑物的固定高度."
        "使用自动高度让周围环境随着树木的生长而生长.",
    "surround_grow": "生长",
    "surround_grow_tt":
        "每年自动增加高度 - 周围的树木与您的树木一起生长.",
    "surround_distance": "距离",
    "surround_distance_tt": "留出生长空间.",

    "stake_enabled": "支柱",
    "stake_enabled_tt": "支柱支撑树干，使其向上直接生长.",
    "stake_height": "高度",
    "stake_height_tt": "支撑树木到这个高度，使树干直立生长.",

    "turn_random": "随机",
    "turn_random_tt": "分支可以自由地沿着随机、不受控制的方向移动，不受光线或重力的引导.",

    "add_chance_reduce": "减少",
    "add_chance_reduce_tt": "降低向不那么旺盛的分支添加新侧枝的机会.减少侧枝的添加将使这些分支积累较少的厚度.最后，这将使较低的遮阳分支并弯曲至地面.",

    # File tool
    'file': "文件",
    "file_tt": "存储供以后使用的树木，或在应用程序之间传输树木.",

    "file_recent": "最近",

    "file_import": "导入树木",
    "file_import_tt": "从 .grove 文件导入模拟.",

    "file_export": "导出树木",
    "file_export_tt": "将当前模拟导出到 .grove 文件.",

    # Roots tool
    "roots": "根",
    "roots_tt": "生成地表根.根通常在地下生长，但可能因土壤侵蚀而暴露.地表根在视觉上令人愉悦，将树木固定在地面上.",

    "roots_roots_panel": "根",
    "roots_number": "数量",
    "roots_number_tt": "主根的数量",
    "roots_nodes": "节点",
    "roots_nodes_tt": "每根主根的节点数",
    "roots_length": "长度",
    "roots_length_tt": "两个节点之间的长度.",
    "roots_climb": "攀升",
    "roots_climb_tt": "使根沿着树干向上生长，形成平滑过渡.",
    "roots_turn_down": "向下生长",
    "roots_turn_down_tt": "",

    "roots_branches_panel": "侧根",
    "roots_branches_panel_tt": "",
    "roots_generations": "代",
    "roots_generations_tt": "添加更多代以更详细地展开根系.",
    "roots_density": "密度",
    "roots_density_tt":
    "生长侧根的机会.要进一步增加密度，增加节点数并减小节间长度.",
    "roots_add_angle": "角度",
    "roots_add_angle_tt": "与主根的夹角.",
    "roots_add_down": "向下添加",
    "roots_add_down_tt": "",

    "roots_variation_panel": "随机",
    "roots_random_heading": "方向",
    "roots_random_heading_tt": "在地面上爬行.",
    "roots_random_pitch": "俯仰",
    "roots_random_pitch_tt": "在生长过程中向上和向下转动.",
    "roots_random_seed": "种子",
    "roots_random_seed_tt": "",

    "roots_thickness_panel": "厚度",
    "roots_thickness": "厚度",
    "roots_thickness_tt": "主根的平均厚度.",
    "roots_thickness_reduce": "减少",
    "roots_thickness_reduce_tt": "",
    "roots_thickness_random": "随机",
    "roots_thickness_random_tt": "",

    "roots_terrain_panel": "地形",
    "roots_terrain_panel_tt": "",
    "roots_drop": "下落",
    "roots_drop_tt": "",

    "restart_single_tree": "单棵树",
    "restart_single_tree_tt": "移除占位符并在原点种植一棵树.",

    "restart_revert": "重新开始",
    "restart_revert_tt": "将所有内容重置为默认值，重新加载当前预设并从一棵树开始.",

    # Plant operator.
    "plant": "种植",
    "plant_tt":
    "种植一组树木 - 创建果园、灌木篱笆或天然树岛."
    "此工具创建空对象，您可以自由移动、复制或删除.",

    "plant_layout": "布局",
    "plant_layout_tt": "种植果园、种植园、灌木篱笆、环形或天然树丛",

    "plant_trees": "树木",
    "plant_trees_tt": "树木数量",

    "plant_space": "间距",
    "plant_space_tt": "树木之间的距离",

    "plant_random_shift": "随机位移",
    "plant_random_shift_tt": "不规则放置",

    "plant_random_seed": "随机种子",
    "plant_random_seed_tt": "改变随机位移",

    "plant_delay": "延迟",
    "plant_delay_tt": "离中心较远的树木在较晚的年份开始生长.",

    "plant_ring_radius": "半径",
    "plant_ring_radius_tt": "环的中心到边缘的距离",

    "plant_rows_trees_tt": "每行树木数量",

    "plant_rows": "行数",
    "plant_rows_tt": "行数",

    "plant_rows_space": "间距",
    "plant_rows_space_tt": "行之间的空间",

    "plant_rows_diagonal": "对角线",
    "plant_rows_diagonal_tt": "将每第二行移位以形成菱形图案",

    "plant_islands_trees_tt": "每个岛屿的平均树木数量",

    "plant_islands": "岛屿",
    "plant_islands_tt": "树木岛屿数量",

    "plant_islands_space": "岛屿间距",
    "plant_islands_space_tt": "树木岛屿之间的平均距离",

    "plant_islands_clearing": "空地",
    "plant_islands_clearing_tt": "中间的开阔空地",

    "plant_islands_randomize": "随机",
    "plant_islands_randomize_tt": "改变每个岛屿的树木数量",

    "plant_layout_clump": "丛",
    "plant_layout_rows": "行",
    "plant_layout_ring": "环",
    "plant_layout_islands": "岛屿",

    "plant_variation_panel": "变化",
    "plant_diverge": "分散",
    "plant_diverge_tt": "远离附近的树木.",

    "plant_terrain_panel": "地形",
    "plant_terrain_drop": "下降",
    "plant_terrain_drop_tt": "将树木投影到地面.",

    "plant_terrain_slope": "坡度",
    "plant_terrain_slope_tt": "在旋转中考虑地形的坡度.",

    "escape_to_stop": "按ESC键停止",

    "restart_all": "重新开始所有",
    "restart_all_tt": "重新开始每个树丛集合.",

    "wind_breeze": "微风",
    "wind_breeze_tt":
    "用生动的微风动画为小树枝注入生命."
    "您可以将其与常规风动画结合使用以产生更强的变形.",

    "favor_end_reduce": "减少",
    "favor_end_reduce_tt":
    "当树枝以垂直角度生长时，减少顶端优先的影响.",

    "widget_scale": "控件缩放",
    "widget_scale_tt":
    "如果屏幕上的径向UI控件过小或过大，请调整它们的大小.",

    'wind_frequency': '风频率',
    'wind_frequency_tt':
        '指风的频率.',
    
    "sow_enabled": "播种",
    "sow_enabled_tt": "在现有老树周围散播种子，模拟自然扩展的树林。",
    
    "sow_age": "延迟",
    "sow_age_tt": "树木需要几年时间生根并建立能量正平衡状态，然后才开始产生种子。",
    
    "sow_chance": "概率",
    "sow_chance_tt":
        "每年每棵树创造成功后代的概率。"
        "实际上，某些树木每年可能产生数千颗种子，其中数百颗可能发芽。"
        "但几乎没有一颗能存活并长成适当的树木。"
        "为了保持模拟以可用的速度运行，请保持较低的概率。",
    
    "sow_distance": "距离",
    "sow_distance_tt": "种子在现有树木周围的一定距离内散播。",
    
    "sow_limit": "限制",
    "sow_limit_tt": "最大树木数量。超过此数量后停止添加新树，以保持模拟平稳运行。",
}
