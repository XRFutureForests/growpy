# coding=utf-8

dictionary = {

    '': '',

    # Panel titles
    'panel_presets': 'プリセット',
    'panel_twigs': '小枝',
    'panel_twigs_more': 'その他',
    'panel_simulation': 'シミュレート',
    'panel_auto_prune': '自動剪定',
    'panel_favor': '優先',
    'panel_drop': 'ドロップ',
    'panel_add': '追加',
    'panel_grow': '成長',
    'panel_turn': '回す',
    'panel_react': '反映',
    'panel_thicken': '濃くする',
    'panel_bend': '曲がる',
    'panel_shade': '日陰',
    'panel_build': '構築',
    'panel_build_wind': '風',
    'panel_build_mesh': 'ポリゴン',
    'panel_build_texture': 'テクスチャ',

    # User preferences
    'set_presets_path': 'プリセットフォルダを設定する…',
    'presets_path': 'プリセットフォルダ',
    'presets_path_tt':
        'プリセットを保存するフォルダを選択してください。このフォルダ内のすべてのプリセットがプリセット選択メニューに表示されます。',
    'set_twigs_path': '小枝のフォルダを設定する…',
    'twigs_path': '小枝のフォルダ',
    'twigs_path_tt':
        '小枝を保存したフォルダを指す。これらの小枝は検出器に羅列される。',
    'set_textures_path': 'テクスチャフォルダーを設定する…',
    'textures_path': 
        '樹皮テクスチャフォルダー',
    'textures_path_tt':
        '樹皮テクスチャーを保存したフォルダを指す。これらのテクスチャーは検出器に羅列される。',
    'widget_scale': 'UIウィジェットのスケール',
    'widget_scale_tt': 
        '画面に合わせて、ラジアルUIウィジェットのサイズを調整してください。小さすぎる場合や大きすぎる場合には、サイズを調整してください。',

    'save_preferences': '環境設定を保存',
    'save_preferences_tt': 'この設定を記憶するために環境設定を保存してください。',


    # Interface messages
    'remove_preset_info': '{}を取り除くか?',
    'overwrite_preset_info': '{}をオーバーライトか?',
    'name_preset_info': 'プリセットに名前を付ける。',
    'height_info': '{:.1f}メートル',
    'age_info': '{}年',
    'branch_info': '{}枝',
    'branches_info': '{:,}枝',
    'polygons_info': '{:,}面',
    'tips_info': 'ツールチップをお読みください:',


    # Presets
    'presets_menu': '',  # Read
    'presets_menu_tt': '樹の種のプリセットパラメータをロードする',

    'preset_name': '新しい名称',
    'preset_name_tt': '保存又はオーバーライト用のプリセット名称',

    'remove_preset': '取り除く',
    'remove_preset_tt': 'プリセットを取り除く',

    'cancel_action': 'キャンセル',

    'remove_preset_confirm': '削除',
    'remove_preset_confirm_tt': 'プリセットの削除を確認',

    'rename_preset': 'リネーム',
    'rename_preset_tt': 'プリセットをリネーム',

    'add_preset': '追加',
    'add_preset_tt': '新しいプリセットを追加、 名前が存在する場合はプリセットを置き換えます。',

    'overwrite_preset': '上書き',
    'overwrite_preset_tt': 'プリセットを上書き',

    'overwrite_preset_confirm': '上書き',
    'overwrite_preset_confirm_tt': 'プリセットの上書きを確認',

    'save_preset': 'セーブ',
    'save_preset_tt': '現在の性質をプリセットとして保存',


    # Simulate
    'simulation_flushes': 'サイクル',
    'simulation_flushes_tt':
        '成長する年数を追加'
        '小さいインタラクティブのステップを使ってあなたの樹をシミュレーションする。 '
        '各ステップの後、 木を制御するために剪定することが可能です、 '
        '木のパラメーターを調整したり、 成長する環境を変更したりすることもできます。',

    'zoom': 'ビュー',
    'zoom_tt': '全体の木のサイズを合わせるためにはスケーリングする',

    'simulate': '成長',
    'simulate_tt':
        '木を成長させる'
        'インタラクティブなステップで成長、 回転、 曲げ、 流れ、 剪定して季節をシミュレーションする。 '
        'あなたの木が一年ごとに成長しつつあることを見る。',

    'restart': '再スタート',
    'restart_tt':
        '木を取り除き再スタート。'
        'あなたの木の特徴を調整するのは試行錯誤のプロセスだ。 '
        'あなたの設置が全部正しいとしても、 大自然は完璧ではない。 '
        '成長、 調整、 再スタート、 リピート…、 これは木が成長する方式だ。',

    'manual_prune': '刈り込む',
    'manual_prune_tt':
        'ウィンドウに切断線を引いて、 枝を削除または短縮します。',

    # Favor
    'favor_end': '先端',
    'favor_end_tt':
        '「先端優先」は、 木の先端に新しい側枝より有利なスタートを与えます。 '
        '短くて弱い側枝を作って始まりますが、 有利なスタートは勝利を保証するものではありません。 '
        '「光優先」が引き継ぎ、 ゆっくりと最高の性能を支持するオッズに変えて、  - '
        '短い側の小枝が追いつくか、 新しい先頭として引き継ぐことさえ可能にします。 '
        '「先端優先」と「光優先」は、 木の最も重要な特徴の2つです。 '
        'それらは連携して、 さまざまな形や特徴を作成します。',

    'favor_end_reduce': '減らす',
    'favor_end_reduce_tt':
        '垂直からの角度で枝が成長する場合、先端効果を軽減する。',

    'favor_bright': '光',
    'favor_bright_tt':
        '木の小枝を何千もの植物として想像してください。'
        '明るいものは大きく成長し、 暗いものは死にます-これは最大限の「光優先」です。'
        '今度は植物を枝でつなぎます-植物の利益を共有する方法を与えます。'
        '糖類が自由に流れて光が豊富な場合、 日陰の植物でさえ、 成長や新しい光を見つけるために必要なサポートを受けます。',

    # Drop
    'auto_prune_low': '低い',
    'auto_prune_low_tt':
        '低い幹枝を刈り込む。'
        '自動的に都市用樹の下部分を刈り込むことで歩行者と交通自由通行できる。'
        '地面に落ちて壊れた幹枝。または動物に奪われた幹枝。'
        '樹が高くなった時に刈り込むはどんどん機能する。',

    'auto_prune_keep_thick': '太いものを持つ',
    'auto_prune_keep_thick_tt':
        '細い枝だけを剪定し、 太い枝を持つ。'
        'これにより、 木はいくつかの大きな主要な枝を成長させ、 木をより自然に見せることができます。'
        '公園のような広いスペースにある木を剪定するときに造園家が目指す外観。'
        '自然界で同じです、 採餌動物は多汁で新鮮な枝を好み、 太い枝はそのままにしておきます。',

    'auto_prune_dangling': '垂れ下がる',
    'auto_prune_dangling_tt':
        '自動剪定の高さよりも少し上の枝は横に伸び、重みによって下に垂れます。'
        'この垂れ下がる枝を、しだれ柳のように伸ばすこともできますが、新しいパラメーター「垂れ下がり」で一定の高さに切り詰めることもできます。'
        'これは、鹿やキリンなどの動物が届く高さと考えることもできます。',

    'drop_shaded': '日陰になった小枝',
    'drop_shaded_tt':
        'シャドウされた幹枝が落ちる。'
        '毎年に樹がそれぞれの方向に数え切れない新しい枝を生み出す。'
        'これらの敏感な小枝が新しい空間や光を探す。'
        'そして樹がそのエネルギーを光がある枝に投入し、 同時に多いシャドウされた小枝を落とす。'
        'このパラメーターを小さくすると更に多い幹枝を保留し、 より濃密な木が生えてくる。'
        'このパラメーターは1まで増やせば更に光がある幹枝を落とせ、 明るく広い木が生長できる。',

    'drop_decay': 'しばらく保存する',
    'drop_decay_tt':
        '死んでいる幹枝を木の上に残る。'
        '死んでいる幹枝が腐くなって木の上から落ちるまでは時間がかかる。'
        '枝が低い部分には、 死んでいる幹枝が集めっている。',

    'drop_weak': '強度が低い先端',
    'drop_weak_tt':
        '枝の末端より低い所で花ができるそして長さの成長が停止する成長の強さ。'
        '高強度の幹枝は木の成長が新しい高さを成長させる。'
        'より低い強度の幹枝のエンドは花や果実が出るという用途がある。'
        'このパラメーターは幹枝の長さの成長を止め、 側面の枝が代わる。'
        'より高い値が花が咲く確率を高める。',

    # Add
    "add_side_branches": "芽",
    "add_side_branches_tt":
        "各ノードの芽の数は、枝の幾何学的配置に直接影響します。交互、対向、"
        "輪生パターンはそれぞれ1つ、2つ、3〜6つの芽に対応します。"
        "成長の勢いと確率が組み合わさり、これらの芽のうちいくつが実際に新しい枝に発達するかが決まります。",

    'add_chance': '確率',
    'add_chance_tt':
        '若い節点で新しい枝を生み出す確率。'
        'すべての芽は新しい幹枝を生み出すではない。'
        '一部は霜害や虫が壊され、 一部は「主流に偏る」が抑制された。',

    'add_chance_reduce': '減らす',
    'add_chance_reduce_tt':
        '成長が鈍い枝に横枝を生やす確率を下げます。横枝を少なくすることで、これらの枝の太さを抑えることができます。'
        '最終的には、より日陰になる下の枝が発生し、地面に向かって垂れ下がるのを防ぐことができます。',

    'add_bud_life': '芽の寿命',
    'add_bud_life_tt':
        '多数の樹にとって、 芽はただ数年感で生きれる。'
        '年齢に達して新しい小枝が出る。'
        '一部の樹にとって,ほぼすべての芽がオープンで ,そして ほぼ頂点優勢の制限がある短い小枝を生み出せる。'
        'この中で多数の小枝は死んでしまい,少ない枝は抑えされなく新しい幹枝を生み出す。',

    'add_only_on_end': '先端のみ',
    'add_only_on_end_tt':
        'エンドの節点だけに新しい幹枝を追加。'
        '針葉樹等はホルモンの成長を抑える。'
        '実際にはエンドに近い節点にはホルモンがない,新しい幹枝が出る。',

    'add_fork': '分岐点',
    'add_fork_tt':
        '枝が特に強く、 活発に成長するとき、 その枝は先端の芽を圧倒する先端の近くでいくつかの芽を発育させることができます。'
        '次に、 枝はいくつかの等しい強度の枝に分割されます.　中央に支配的な枝がない場合、 分岐枝は通常の半分の角度で成長します。'
        '明確な単一の幹を形成する代わりに、 分岐した木は主要な枝の広がり構造を作成します。',

    # Grow
    'grow_length': '長さ',
    'grow_length_tt': '新しい成長できた長さ',

    'grow_nodes': '節点',
    'grow_nodes_tt':
        '幹枝は毎年に成長できる最大の節点の数。低い強度はより少ない節点が成長できる。',


    # Turn
    'turn_up': '上向き',
    'turn_up_tt': '負の重力屈性。新しい枝は重力から離れて上向きに成長します。負の値を使用すると下向きに成長します。',

    'turn_up_in_shade': '陰影で上向き',
    'turn_up_in_shade_tt': '日陰の成長は重力から離れて上向きにします。負の値を使用すると下向きに成長します。',

    'turn_to_light': '向光性',
    'turn_to_light_tt':
        '向光性。'
        '一番明るい方向に新しい成長させる。'
        'これは室内の植物が窓口へ成長させる効果がある。'
        '樹にとって、 この効果は幹枝の配分を改善できる。',

    'turn_to_horizon': '地平線へ',
    'turn_to_horizon_tt':
        '斜生。'
        '幹枝はシャドウされた時に地平線へ向く。',

    'turn_random': 'ランダム',
    'turn_random_tt':
        '枝がランダムで自由に動くようになります。光や重力による誘導がないため、予測不可能な方向に動きます。',

    # Add
    'add_horizontal': '水平',
    'add_horizontal_tt':
        '芽の斜生。'
        '葉序角は水平方向へのステアリング。',

    'add_angle': '角度',
    'add_angle_tt':
        '新しい幹枝及び親幹枝との角度。'
        '角度範囲は幹枝の延長線から親幹枝までの「0° - 90°」間の角度。',

    'add_twist': 'ツイスト',
    'add_twist_tt':
        'すべて接続節点をツイスト。'
        '橡の木等の樹は著しいツイストがある、 '
        '幹枝の部分でよくツイストがある模様を見れる。'
        '著しい見る品質を除き、 芽の葉序ツイストを増やす。'
        'このパラメーターは分枝の木にある幹枝の配分を改善できる。',


    # Interact
    'react_block_object': '断ちきる',
    'react_block_object_tt':
        '環境対象と衝突した後に成長を止めた。',

    'react_shade_object': '日陰',
    'react_shade_object_tt':
        '環境の対象はシャドウを生じ,光のパラメーターに影響を与える。',

    'react_deflect_object': '偏向',
    'react_deflect_object_tt': '環境の対象を避ける。',

    'react_attract_object': '吸引する',
    'react_attract_object_tt':
        '環境の対象への成長する。'
        '枝は対象を抜けて自由に成長できる。',

    'react_vigor_object': '强度',
    'react_vigor_object_tt':
        '新しい成長の活力を制御するオブジェクトを選択する。',

    'react_force': '力',
    'react_force_tt':
        'オブジェクトが木に及ぼす力の大きさです。',

    "react_falloff": "減衰",
    "react_falloff_tt":
        "効果はオブジェクトに近いほど強く、反応するオブジェクトからの距離に指数関数的に減衰します.",


    # Thicken
    'thicken_tips': '端末',
    'thicken_tips_tt':
        '幹枝の端末の直径を指す。'
        'これは幹枝が強い強度があるときの端末の太さ。'
        'より低い強度がある幹枝は太さを減少させる。',

    'thicken_tips_reduce': '減少',
    'thicken_tips_reduce_tt':
        '低い強度の幹枝の端末の太さを減少させる。'
        '強度が低い枝はより細くなります．'
        'このパラメーターは木の形状を影響に与える,理由としては細い幹枝が曲がり安い 。'
        '針葉樹の形状により多く影響される。',

    'thicken_join': '幹枝に接続する',  # Grow or Merge or Join or Reinforce
    'thicken_join_tt':
        'より厚くなります。'
        '太さは先端から増やす。'
        '二つの枝が接続する時に、 両者のクロス部分は増やし、 更に太い幹枝を作れる。'
        'こういう行為は木のベースまで持続できる。'
        '幹枝の太さ成長スピードを変えあなたの木の形状を変える。'
        '増やした太さは幹枝を強化させ曲がることを減少する。',

    'thicken_base_scale': 'ベースの比例',
    'thicken_base_scale_tt':
        'ベースの太さを増やす。'
        '幹枝の根の所で、 根が成長することによって根のところの太さを増やす。',

    'thicken_base_shape': '形状',
    'thicken_base_shape_tt':
        '「根の比例」を調整し幹枝の形状をゆっくりで融合させる。',

    'thicken_base_buttress': '根の突き',
    'thicken_base_buttress_tt':
        '根の突きが付き多様「根の比例」。',

    'root_distribution': '分布する',
    'root_distribution_tt':
        '幹枝の「根比例」効果の到着率。',

    'roots': '根',
    'roots_tt':
        '表層根を生成します。根は通常、地面の下に成長しますが、土壌の浸食によって露出することがあります。見た目が良く、表層根は木を地面に固定します。',

    'roots_roots_panel': '根',
    'roots_number': '数',
    'roots_number_tt': '主根の数',
    'roots_nodes': 'ノード',
    'roots_nodes_tt': '根あたりのノード数',
    'roots_length': '長さ',
    'roots_length_tt': 'ノード間の長さ',
    'roots_climb': '登る',
    'roots_climb_tt': '幹に沿って根を登らせて、スムーズなブレンドを作成します。',
    'roots_turn_down': '下向き',
    'roots_turn_down_tt': '',

    'roots_branches_panel': '側根',
    'roots_branches_panel_tt': '',
    'roots_generations': '世代数',
    'roots_generations_tt': 'より詳細な根系を展開するために、より多くの世代を追加します',
    'roots_density': '密度',
    'roots_density_tt':
        '各ノードに側根を成長させる確率',
    'roots_add_angle': '角度',
    'roots_add_angle_tt': '主根と側根の間の角度',
    'roots_add_down': '下向き',
    'roots_add_down_tt': '',

    'roots_variation_panel': 'ランダム',
    'roots_random_heading': '方向',
    'roots_random_heading_tt': 'ランダムに地面を這い回る',
    'roots_random_pitch': '傾斜角',
    'roots_random_pitch_tt': 'ランダムに上下に曲げる',
    'roots_random_seed': 'ランダムシード',
    'roots_random_seed_tt': '',

    'roots_thickness_panel': '濃くする',
    'roots_thickness': '太さ',
    'roots_thickness_tt': 'メインルートの平均太さ',
    'roots_thickness_reduce': '減らす',
    'roots_thickness_reduce_tt': '',
    'roots_thickness_random': 'ランダム',
    'roots_thickness_random_tt': '',

    'roots_terrain_panel': '地形',
    'roots_terrain_panel_tt': '',
    'roots_drop': '地形への落下',
    'roots_drop_tt': '',

    # Bend
    'bend_mass': '幹枝の曲げ量',
    'bend_mass_tt':
        '枝の重みでの曲げ量．'
        '枝の曲がりは木の形に大きな影響を与えます、 特に樹齢が高い場合。'
        '枝の曲がり量は太さによって異なります、  - '
        '太い枝の方が重くなりますが、 断面積が大きくなると、 指数関数的に強くなります。',

    'bend_twig_mass': '枝先の曲げ量',
    'bend_twig_mass_tt':
        '葉の重みでの曲げ量'
        '枝の端末はより重い重量を受けれる、 これらの重量は葉や花、 果実付き葉からだ。'
        '木は負の重力屈性で上向きに成長することによって、 この曲がりに対抗します。'
        '曲がりと重力屈性間の影響は帚状樹体又は垂枝型に重要な役割を果たす。',

    'bend_twig_mass_solidify': '固化',
    'bend_twig_mass_solidify_tt':
        '枝の端を引き下げることによる曲がりを固めます。この重さは季節によって異なり、 重い春の花、 大きな葉、 分厚い果実はすべて枝を引き下げます。'
        'しかし、 枝が固くなる時が来ると、 この重さのほとんど落ちているかもしれません。'
        'したがって、 多くの場合、 この「固化」パラメータは枝の重みを固化するために使用されるパラメータよりも小さくなります。',

    'bend_reaction': '反応',
    'bend_reaction_tt': '反応木材は成長の強い枝を時間とともに積極的に後へ曲げます。',


    # Shade
    'shade_area': '葉の面積',
    'shade_area_tt':
        '幹枝端末のシャドウ面積、 dm²を単位にする。'
        '根は4.0「葉の面積」は10cm x 10cmの面積の4倍になる。'
        'ご注意してください、 これは小枝の複合面積で,単なる葉の面積ではない 。',

    'shade_area_reduce': '縮小',
    'shade_area_reduce_tt': '強度が低い枝の葉面積を減らす。',

    'shade_area_depth': '深さ',
    'shade_area_depth_tt':
        '日陰キャスターの側面を持ち上げて、 形をより深くします。'
        'これにより、 木の側面からより多くの日陰が発生し、 一般的に日陰が増えます。'
        '落下日陰を減らすことで補償できます。'
        '日陰プレビューを有効にして、 効果を確認します。',

    'shade_leaf_sides': '側面',
    'shade_leaf_sides_tt':
        'また、 枝の側面に沿って日陰の葉の領域を分散させます。'
        '枝の端に葉があり、 うまく機能する小さな抽象化でほとんどの木はシミュレートできます。'
        'しかし、 しだれ枝のある木では、 側枝が必要です。'
        'これには、 より小さな葉面積が必要であることに注意してください、 より多くの小枝が配置されるため。',

    'tweak': '微調整',
    'tweak_tt': 'これらのパラメータを 3D ビューポート上でビジュアルに調整します。',


    # Build
    'rebuild': '構築',
    'rebuild_tt': '木模型のメッシュを再構築します。木を再構築して、 ポリゴンの縮小、 頂点レイヤー、 太さのスケール、 および側面小枝の分布を更新します。',

    'smooth': '滑らかに',
    'smooth_tt':
        '鋭い角の角度を小さくすると、 より滑らかに曲がった枝を作成します。',

    'build_resolution': '分解能',
    'build_resolution_tt':
       '木の根元（最も太いところ）にある頂点の数です。',

    'build_resolution_reduce': '削減',
    'build_resolution_reduce_tt':
        '細い枝にあるポリゴンを削減する．'
        '木のポリゴンの大部分は数えない若い枝の中にある。'
        '視覚の品質を壊れない前提でこれらの細い幹枝は少ないポリゴンを使える。',

    'texture_bark': '樹皮のテクスチャー',
    'texture_bark_tt':
        'テクスチャーを取る',

    'texture_repeat': 'UVリピート',
    'texture_repeat_tt':
        '樹のベースの週長に樹の皮テクスチャーの数 - '
        'より細い枝で自動的に減少する。',

    'simulation_scale':
        'スケール',
    'simulation_scale_tt':
        'プリセットを違う小枝の大きさに適応する。'
        '一つ普通の小枝は1年間または2年間の成長を含み、 約30cmの長さがある。'
        'プリセットは大きさに適応させる。ただし小枝模型は好きな大きさを調整でき、 シングルな葉から数年の成長まで全部できる。'
        '違うサイズを調整する方式は簡単に比例で小枝の模型を拡大または縮小する。'
        'この操作は同じ比例であなたの小枝を保留できる。',


    # Twigs
    'twig_menu': '小枝',  # Twigs, Library
    'twig_menu_tt':
        '一組の小枝を取りあなたの樹に飾る。'
        'このメニューには、 枝フォルダにあるすべての枝が一覧表示されます-'
        'Groveでユーザーのオプションからフォルダを選択できる。'
        '現在のシーンからオブジェクトを選択することもできます。',

    'twig_pick_objects': 'シーンの対象',
    'twig_pick_objects_tt': 'シーン中の3D对象を取る。',

    'twig_no_twigs': '小枝が無い',
    'twig_no_twigs_tt': '小枝が無い',

    'twig_object_end': '先端',
    'twig_object_end_tt':
        '幹枝の端末ところで分布された小枝の対象。'
        '先端小枝は、 葉、 時には花か後に果実を伴う新しい成長です。'
        '先端小枝は既存の枝の延長です-側枝よりもはるかに強く、 長いのが多いです。',

    'twig_object_side': '側面',
    'twig_object_side_tt':
        '幹枝の側面に沿って分布される小枝対象を指す。'
        '側枝は既存の枝の側面に沿って成長する新しい枝です。'
        '彼らは葉、 時には花と後に果物を持ってます。'
        '側枝は多くの場合、 先端枝よりも短いです、 作成するリードブランチにホルモン抑制があるから。'
        '最終、 最強のものだけが完全な新しい枝に成長します。',

    'twig_object_upward': '上向き',
    'twig_object_upward_tt':
        '急に上向きに成長しているときに端の小枝ををオプションの小枝模型。'
        'これらの小枝はさらに長く、 葉があらゆる方向にねじれています。 '
        '小枝が設定されていない場合、 先端の小枝が使用されます。',

    'twig_object_dead': '死亡',
    'twig_object_dead_tt':
        'オプションの小枝モデルです、 死んだ小枝である場合、 他のすべての小枝を覆す。'
        '小枝が設定されていない場合、 小枝は死んだ小枝に使用されなく、 低強度部分の詳細が失われます。',

    'twig_density': '密度',
    'twig_density_tt':
        '多くか少なくな側面の小枝を追加することにより、 木の葉の密度を制御します。',

    'twig_view_detail': 'ビューの詳細',
    'twig_view_detail_tt':
        '小枝のディスプレイ解像度を低くする。'
        'よりよいウィンドウズ性能を獲得できるように、 このパラメーターは全ての小枝模型に「ポリゴン数削減」修正器を添加する。'
        'ウィンドウズは低い解像度模型を使う - レンダリングエンジンにはオリジナルモデルを使う状況に対して。',

    'twig_pick_collections': 'コレクション',
    'twig_pick_collections_tt': '現在のファイルで任意の枝のコレクションをピックする。',

    'twig_side_on_tips': '先端の側面',
    'twig_side_on_tips_tt':
        'すべての枝の先端で、 先端の小枝の隣に、 側小枝も配置します。'
        '再構築すると効果が表示します。',

    'twig_hide': '',
    'twig_hide_tt': '小枝を一時的に隠して、 分枝の構造がよく見えます。',

    'twig_longevity': '生命',
    'twig_longevity_tt':
        'すべての枝の先端の近くで若い側小枝を複製します。'
        'パラメーターを増加すると、 小枝がますます古くて太い枝の部分に現れます。'
        '効果が表示するには再構築が必要です。',

    'twig_wither': '枯れ',
    'twig_wither_tt':
        '枯れた小枝が木にくっついて枯れる年数(生後).\n'
        '効果が表示するには再構築が必要です。',

    'use_adaptive_units': '適応単位を使います．',
    'use_adaptive_units_tt':
        'Groveのパラメーターのいくつかに単位を使用します.そのいくつかは、 小さな距離を表します。'
        '適応単位を有効にすると、 0.001mは1mmとして表示されます。',

    'language': '言語',
    'language_tt': 'インタフェースとツールに使う言語',

    'favor_rising': '上昇',
    'favor_rising_tt':
        '垂れ下がった幹枝より上昇する幹枝に好む。'
        '上へ枝を促進すると高い木を獲得する。'
        '値は1の时に水平な幹枝の強さをゼロにする。',


    # New
    'grove': 'Grove',

    'label_direction': '開始方向',

    'add_new_grove': '木立を追加',
    'add_new_grove_tt': '木立コレクションを追加。',

    "select_a_grove_collection": "木立コレクション選択",

    'select_linked_branches_tt': '現在の選択を全体やサブブランチの枝に展開する。',
    'select_linked_branches': 'リンクされている枝を選択する',

    "select_thicker": "太い枝の部分を選択",
    "select_thicker_tt": "枝のうち、しきい値値より太い部分を選択します.",
    "select_thicker_threshold": "より厚い",

    'show_dead_preview': '死んだことを表示する',

    'disable_outline': '輪郭無効にする',
    'disable_outline_tt':
        '木を正しく表現し、 微調整中の視覚的なフィードバックを改善するため、 輪郭無効にします。'
        '輪郭陰影は枝を実際よりはるかに太く見えます。',

    'set_background': '背景を明るくする',
    'set_background_tt':
        'クリックしてビューポートの背景を明るくし、 中間の灰色に設定します。'
        '枝がはるかに見やすくなり、 木がより良く見えるようになります。',

    'add_up': '上向き',
    'add_up_tt':
        '芽の負の重力屈性 - 新しい枝は重力から離れて上向きに成長します。負の値を使用すると下向きに成長します。',

    'regrow': '再成長',
    'regrow_tt': '再起動して、 現在の年齢まで木をすばやく再成長させます - 構築手順をスキップしますが、 木を剪定する機会もスキップします。',

    'replant_grove': '植え替える',
    'replant_grove_tt': '植え替える。',

    'attribute_age': '年齢',

    'calculate_wind': '動画を設置する',
    'calculate_wind_tt': '風動画を追加する',

    'label_animating_wind': '風ををアニメ化する…',
    'label_stop': '停止',

    'wind_breeze': '風のそよぎ',
    'wind_breeze_tt':
        '軽快な風のアニメーションで枝を生き生きとさせます。通常の風のアニメーションと組み合わせることで、より強い変形を実現できます。',

    'wind_vector': '風',
    'wind_vector_tt': '速度と方向',
    'wind_turbulence': '乱れ',
    'wind_turbulence_tt': '小枝を飛ばし、 枝を風に舞わせます。',

    'wind_shapes': '形キーフレーム',
    'wind_shapes_tt':
        '各形状はキーフレーム二つ離れて流暢に補間されます\n'
        '風は自動的に循環します',

    'import_preset': '種子ファイルを輸入…',
    'import_preset_tt': '.seed.jsonファイルに保存されるプリセットで、 他のユーザーと共有できます - 輸入されると、 プリセットのリストに追加します。',

    'placeholder_delay': '遅延',
    'placeholder_delay_tt': '成長し始める前に待つ年。',

    'panel_build_base': '根元',

    'add_tree': '植え',
    'add_tree_tt':
        '空のオブジェクトを追加してから成長させます。'
        'このオブジェクトを移動、 回転、 複製、 または削除して木のグループを成長させます．それぞれの木は独自の場所と角度を持っている．',

    'old_release_warning_line_1': '古いリリースで育った木。',
    'old_release_warning_line_2': '変更が多くあります。',
    'old_release_warning_line_3': '古いリリースを使用して編集してください。',

    'thicken_deadwood': '枯れた木',
    'thicken_deadwood_tt':
        '落とされたまたは剪定された枝は、 木が部分的に治癒する傷を残します。'
        'しかし、 中核部の一部が死んだ、 新しい成長は、 より多くの厚さを追加することによって木に補償されます。'
        'これで、 時間の経過とともに、 幹の厚みが増します。',

    'grow_together': '一緒に成長',
    'grow_together_tt':
        'すべての別々の果樹園を1つにまとめて育てる．これにより、 異なる樹種を混ぜることができます。'
        '日陰と屈光性の計算を組み合わせて、 光を奪い合うようにします。',

    'draw': '描画',
    'draw_tt': '新しい枝を描画します。パス全体がたどられるまで、 それは年々成長します。',

    'prune_status_draw_lines': '描画',

    'bend_tool_distance': '距離',
    'bend_tool_distance_tt': '',

    # Bend tool
    'manual_bend': '彎曲',
    'manual_bend_tt':
        '金属線で枝を曲げる盆栽技法に着想を得た道具、 しかし、 もっと柔軟性があり、 '
        '最も太い枝でも曲げることができ、 成長した木でもスタイリングすることができます。',

    'bend_tool_bend_button': '屈曲',
    'bend_tool_bend_button_tt': 'スペース',

    'bend_tool_curve': '曲線',
    'bend_tool_curve_tt': '屈曲の形',
    'bend_tool_curve_simple': '简单',
    'bend_tool_curve_flexible': '柔軟',
    'bend_tool_curve_s_curve': 'S型曲線',

    'close_button': '',
    'close_button_tt': '閉じる',

    'turntable': '',
    'turntable_tt': 'ビュー',

    # Record
    'record_enabled': '記録',
    'record_enabled_tt':
        '成長をの一連のオブジェクトとして記録と呼ばれる専用コレクションで記録します。'
        '各ステップは、 短時間だけ表示できるようにキーフレーム化されています.すべてのオブジェクトが順番に成長アニメーションを形成します。',

    'record_interval': '間隔',
    'record_interval_tt':
        '毎年は木の最初の春の形から完全に成長した夏の形まで、 流暢な補間が行われます。'
        'この補間のフレーム数を定義します-それで成長の速度を定義します。'
        'この値はいつでも微調整できます、 アニメーションはすぐに更新されます。',

    'record_start': '開始フレーム',
    'record_start_tt': 'このフレームから開始するようにアニメーションを時間的に前に移す。',


    # Plant operator.
    'plant': '植える',
    'plant_tt':
        '樹木をグループで植え、果樹園、生け垣、または自然な樹木の島を作成します。このツールは空のオブジェクトを作成し、自由に移動、複製、または削除できます。',

    'plant_layout': 'レイアウト',
    'plant_layout_tt': '果樹園、プランテーション、生け垣、輪または自然な木の塊を植える',

    'plant_trees': '木の数',
    'plant_trees_tt': '木の数',

    'plant_space': '木々の間隔',
    'plant_space_tt': '木々の間隔',

    'plant_random_shift': 'ランダムシフト',
    'plant_random_shift_tt': 'より自然な配置を得るために、ランダムに木を移動します',

    'plant_random_seed': 'ランダムシード',
    'plant_random_seed_tt': 'ランダムな配置を取得するために、ランダムシードを変更します',

    'plant_delay': '待機',
    'plant_delay_tt': '中心から遠い木々の成長を開始するまでの年数',

    'plant_ring_radius': '半径',
    'plant_ring_radius_tt': 'リング中心からの距離',

    'plant_rows_trees_tt': '1列あたりの木の数',

    'plant_rows': '木の列',
    'plant_rows_tt': '行の数',

    'plant_rows_space': '間隔',
    'plant_rows_space_tt': '樹木間のスペース',

    'plant_rows_diagonal': '斜めの線',
    'plant_rows_diagonal_tt': '2行目をずらして菱形のパターンにする',

    'plant_islands_trees_tt': '各島にある木の平均数',

    'plant_islands': '木の島',
    'plant_islands_tt': '木の島の数',

    'plant_islands_space': '島と島の間の間隔',
    'plant_islands_space_tt': '木の島同士の平均距離',

    'plant_islands_clearing': '森林伐採',
    'plant_islands_clearing_tt': '中央の空きスペース',

    'plant_islands_randomize': 'ランダム',
    'plant_islands_randomize_tt': '島ごとに木の数を変える',

    'plant_layout_clump': '木の塊',
    'plant_layout_rows': '木の列',
    'plant_layout_ring': '木の輪',
    'plant_layout_islands': '樹木の自然な島',

    'plant_variation_panel': 'バリエーション',
    'plant_diverge': '分散',
    'plant_diverge_tt': '近くの木から離れるように方向を変えます。',

    'plant_terrain_panel': '地形',
    'plant_terrain_drop': '地形への落下',
    'plant_terrain_drop_tt': '地上に木を投影する',

    'plant_terrain_slope': '地形に沿う',
    'plant_terrain_slope_tt': '地形の曲率に従う',

    'grow_tool_growing': '成長中',
    'grow_tool_growing_tt': 'Escキーでキャンセル。',
    'grow_tool_building': 'メッシュを構築中',

    'drop_obsolete': '廃止',
    'drop_obsolete_tt':
        '木が成長するにつれて、 下の枝は陰になり、 小さな枝は落ちます。'
        '古い主枝は減少する葉をサポートするために必要よりも太くなります。'
        'この余分な木材を支えることができず、 枝はやがて退化になり、 腐敗し、 落下します。'
        'これは、 大量の手動剪定後にも発生します。',

    'add_regenerate': '再生',
    'add_regenerate_tt':
        '再生芽は、 大きな剪定または自然損傷の後に枝に沿ってさらに形成されます。'
        '支える葉が少ない場合、 余分な木のエネルギーは古い休眠中の芽に木を修復し、 隙間を埋める2度目のチャンスを与えます。'
        '針葉樹種が再生芽をあまり形成しません。',

    'stake_enabled': '支柱',
    'stake_enabled_tt': '木の幹を支える杭で、まっすぐ成長させます。',
    'stake_height': '高さ',
    'stake_height_tt': '樹幹がまっすぐ育つよう、この高さまで支持する。',

    # Surround
    'surround_enabled': '囲む',
    'surround_enabled_tt':
        '林内に成長する木をシミュレートするため、木々を周囲からシェードで覆います。'
        '全体の森を成長させる必要はなく、単一の木を周囲と同じ環境に置くことができます。'
        '森の中で育つ木々は、より高く細く伸び、下部の枝を早く失います。',

    'surround_density': '密度',
    'surround_density_tt':
        '広い野原、密林、あるいはその中間のどこかで木を育てましょう。',
    'surround_height': '高さ',
    'surround_height_tt':
        '周りの建物や成木の影をシミュレーションするための固定高さです。自動高さを使用すると、周囲の木々があなたの木と一緒に成長するようになります。',
    'surround_grow': '育てる',
    'surround_grow_tt':
        '毎年高さが自動的に増加します。周囲の木々も一緒に成長します。',
    'surround_distance': '半径',
    'surround_distance_tt': 'あなたの木から周囲の植生までの距離。',

    # File tool
    'file': 'ファイル',
    'file_tt': '後で使用するために木を保存したり、異なるアプリケーション間で木を転送したりします。',

    'file_import': '木のインポート',
    'file_import_tt': '.groveファイルからシミュレーションをインポートします',

    'file_export': '木をエクスポートする',
    'file_export_tt': '現在のシミュレーションを .grove ファイルにエクスポートする',

    'escape_to_stop': 'UIウィジェットのスケール',


    # Old and unused
    'shade_sensitivity': '敏感度',
    'shade_sensitivity_tt':
        'シャドウの敏感度を指す。'
        'シャドウは明るいからくらいまでの線形値、 しかし大自然は指数の方式で反応させる。'
        '0をシャドウの反応を設定し、 幹枝は多いシャドウを受けてから反応する。'
        '1を即時反応を設定し,そうしたら一つのシャドウでも拡大しない 。',

    'shade_elongation': '日陰で長く',
    'shade_elongation_tt':
        'シャドウされる幹枝の成長は長い又は短いケースもある。'
        'シャドウで成長している植物は光を探したい,だから長く成長できる。'
        'このパラメーターは太さにより、 より長く弱い曲がりが多いの樹を作れる。'
        'このパラメーターはよく頂点に見れる幹枝が出る。',

    'wind_frequency': '風の頻度',
    'wind_frequency_tt':
        '風の頻度を指す。',

    'branching_inefficiency': '効率が低い',
    'branching_inefficiency_tt':
        'これは子枝や子枝に繋がる成長強度を制限する直接的な方法だ。'
        '枝の付属部分に欠陥があるので、 水分の輸送を制限する。',

    'sapwood': '辺材',
    'sapwood_tt':
        '木の太さを指す。辺材は水分を輸送する木だ。'
        '枝干のコア部分は枯木であり、 支える部分として心材と呼ばれている。'
        'この値を増やすことで太い枝の厚みが少なくなる。',

    'Placeholder': 'プレースホルダー',

    'shade_avoidance': 'シャドウ強化',
    'shade_avoidance_tt':
        '影付きの枝で「先端優先」を増減します。'
        '各枝は、 光を見つけるための戦略として、 「先端優先」を制御します。'
        '枝が日陰になっているほど、 日陰から逃れるためにその端の成長を促進するか、 '
        'またはできるだけ多くの薄明かりを取るために側枝の成長を支持することができます。'
        '後者は、 山毛欅や榛树のような林床種で見ることができます。',

    'label_layers': 'レイヤー',
    
    "sow_enabled": "種まき",
    "sow_enabled_tt": "既存の古い木の周りに種を散らし、自然に広がる木々の群れをシミュレートします。",
    
    "sow_age": "遅延",
    "sow_age_tt": "木は種を生産し始める前に、根を張り、エネルギー的にプラスの状態を確立するのに数年かかります。",
    
    "sow_chance": "確率",
    "sow_chance_tt":
        "各木が毎年成功した子孫を作り出す確率。"
        "実際には、一部の木は毎年何千もの種を作り出し、その何百もの種が発芽することがあります。"
        "しかし、ほとんど生き残って適切な木に成長することはありません。"
        "シミュレーションを使用可能な速度で実行するために、確率を低く保ちます。",
    
    "sow_distance": "距離",
    "sow_distance_tt": "種は既存の木の周りの距離内に散布されます。",
    
    "sow_limit": "制限",
    "sow_limit_tt": "最大木の数。シミュレーションをスムーズに実行するため、この数を超える新しい木の追加を停止します。",
    
    "build_skeleton": "スケルトンを構築",
    "build_skeleton_tt": "ボーン、ボーンウェイトグループ、風のアニメーションを作成します。",
    
    "skeleton": "スケルトン",
    "skeleton_tt": "ボーンを使って木をアニメーション化できるスケルトンを作成します。また、メッシュポイントを対応するボーンにリンクする頂点グループも追加します。オプションで、新しいボーンに風のアニメーションを追加することもできます。",
    
    "skeleton_panel_bones": "ボーン",
    "skeleton_panel_wind": "風",
    
    "skeleton_reduce": "削減",
    "skeleton_reduce_tt": "細い側枝をスキップしてボーン数を減らします。",
    
    "skeleton_bias": "分布",
    "skeleton_bias_tt": "値を増やすと上部にボーンが多く追加され、減らすと下部にボーンが多く追加されます。",
    
    "skeleton_length": "長さ",
    "skeleton_length_tt": "ノードをスキップしてより長いボーンを作成します。",
    
    "skeleton_connected": "連結",
    "skeleton_connected_tt": "Blenderは浮かんでいるボーンからヒエラルキーを構築できますが、他のプログラムでは連結されたボーンチェーンが必要です。この接続には分岐点ごとに新しいボーンが必要で、ボーン数が増加します。",
    
    "file_recent": "最近のファイル",
    
    'auto_prune_enabled': '自動剪定',
    'auto_prune_enabled_tt':
        '自動的に、毎年側枝を剪定して木の基部をクリアにします。'
        'これにより視界がクリアになり、人や交通の自由な通行が可能になります。'
        '地面の霜で傷ついた低い枝を落とし、採食動物によって枝を失います。'
        'この剪定は毎年自動的に行われます。',
    
    'auto_prune_low_message': '木の基部に沿って {} メートル以下の枝を自動的に剪定します',
    
    'add_planar': '平面的',
    'add_planar_tt': '水平回転と同様に、新しい枝が成長方向に平面的に生えます。',
    
    'react_enabled': '反応',
    'react_enabled_tt':
        'メッシュオブジェクトを使用して、新しい成長を引き寄せたり、反らせたり、停止させたりします。'
        '建物に影を落とさせたり、創造的になって形の中に木を成長させたりしましょう。',
    
    'shade_branches': '枝',
    'shade_branches_tt': 'ほとんどの影は葉から来ていますが、一部の木では枝の形状も影の計算に含めることができます。',
    'shade_alongside': '並行',
    'shade_alongside_tt': '新しく成長した小枝に加えて、松などの木は古い針葉が枝の横に残ります。',
    'shade_alongside_diameter': '直径',
    'shade_alongside_diameter_tt': '枝の横に影を落とす形状の直径。',
    
    'shade_branches_panel': '枝',
    'shade_leaves_panel': '葉',
    
    'restart_all': 'すべて再スタート',
    'restart_all_tt': '全ての木立コレクションを再スタートします。',
    
    'close': '閉じる',
    
    'prune_status_do_prune': '剪定',
    
    'restart_single_tree': '単一の木',
    'restart_single_tree_tt':
        'プレースホルダーを削除し、原点に単一の木を植えます。',
    
    'restart_revert': '最初からやり直す',
    'restart_revert_tt':
        'すべてをデフォルトにリセットし、アクティブなプリセットを再ロードして、単一の木で再開します。',
    
    'operator_turntable': 'ビュー',
    'operator_turntable_tt':
        '目の高さから木を見る - 木の周りや下の冠の下を歩き回る。',
    
    'build_triangulate': '三角形化',
    'build_triangulate_tt': '木の枝を構築するのに四角形ではなく三角形のみを使用します。',
    
    'build_cutoff_thickness': '太さカットオフ',
    'build_cutoff_thickness_tt': 'この直径以下のノードの構築をスキップします。',
    
    'build_cutoff_age': '年齢カットオフ',
    'build_cutoff_age_tt':
        '詳細レベルは、ポリゴン数を大幅に減らすために、最後の数年間の成長の構築をスキップします。'
        'これは、同等の年数の成長を表す大きな小枝で補償する必要があります。',
    
    'build_blend': 'ブレンド',
    'build_blend_tt':
        '親枝からスムーズな移行を作成するために追加のノードを追加します。'
        'これは常に太い枝に対して行われますが、ポリゴン数を大幅に減らすために細い枝では無効にすることができます。',
    
    'build_end_cap': 'エンドキャップ',
    'build_end_cap_tt':
        '枝の端を延長点に接続するポリゴンで閉じます。'
        '小枝を使用する場合や適度な距離では、キャップを取り除くとポリゴン数が大幅に減少し、ほとんど目立ちません。',
    
    'detail_simplify': '単純化',
    'detail_simplify_tt':
        '方向にほとんど変化のない直線的なノードをスキップして枝を単純化します。'
        'これはポリゴン数をわずかに減らすだけです。',
    
    'escape_to_stop': '停止するにはEscキーを押してください',
    
    'use_scientific_names': '学名を使用する',
    'use_scientific_names_tt':
        '利用可能な場合、小枝の種を学名で表示します。'
        'オフにすると、小枝メニューには一般的な英語名が表示されます。',
    
    'grow_together_tt_short':
        'すべての木立コレクションを一度に育て、光を争う異なる種を一緒に成長させます。',
    
    'fallback_info': 'アドオンは動作しています',
    'fallback_instructions': '成長の準備をしましょう',
    'fallback_instructions_tt':
        'シミュレーションコアをインストールするには http://www.thegrove3d.com/info/install/ の指示に従ってください。',
    
    'trial_end': '購入する…',
    'trial_end_tt':
        'トライアル期間が終了しました。The Groveが気に入った場合は、ライセンスを購入して素晴らしい木を育て続けてください。',
}
