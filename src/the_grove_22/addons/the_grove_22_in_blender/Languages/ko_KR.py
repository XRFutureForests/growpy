# coding=utf-8

dictionary = {

    "": "",

    # Panel titles
    "panel_presets": "프리셋",
    "panel_twigs": "가지",
    "panel_twigs_more": "더 보기",
    "panel_simulation": "시뮬레이션",
    "panel_react": "반응",
    "panel_favor": "선호",
    "panel_drop": "떨어뜨리기",
    "panel_add": "추가",
    "panel_grow": "성장",
    "panel_turn": "회전",
    "panel_thicken": "두껍게",
    "panel_bend": "굽힘",
    "panel_shade": "그림자",
    "panel_build": "구축",
    "panel_build_wind": "바람",
    "panel_build_mesh": "메시",
    "panel_build_texture": "텍스처",

    # User preferences
    "set_twigs_path": "가지 폴더 설정...",
    "twigs_path": "가지 폴더",
    "twigs_path_tt":
        "가지를 저장하는 폴더를 선택하세요. 이 폴더의 모든 가지가 가지 선택기에 표시됩니다.",

    "set_textures_path": "텍스처 폴더 설정...",
    "textures_path": "나무껍질 텍스처 폴더",
    "textures_path_tt":
        "나무껍질 텍스처를 저장하는 폴더를 선택하세요. 이 폴더의 모든 텍스처가 나무껍질 텍스처 선택기에 표시됩니다.",

    "widget_scale": "위젯 크기",
    "widget_scale_tt":
        "화면에서 너무 작거나 크게 표시되는 경우 원형 UI 위젯의 크기를 조절하세요.",

    # Interface messages
    "remove_preset_info": "{} 삭제하시겠습니까?",
    "overwrite_preset_info": "{} 덮어쓰시겠습니까?",
    "name_preset_info": "프리셋의 이름을 입력하세요.",
    "height_info": "{:.1f} m",
    "age_info": "{} 플러시",
    "branch_info": "{} 가지",
    "branches_info": "{:,} 가지",
    "polygons_info": "{:,} 면",
    "tips_info": "툴팁을 읽어보세요:",

    # Presets
    "presets_menu": "",
    "presets_menu_tt": "나무 종 프리셋 파라미터를 불러오기",

    "preset_name": "새 이름",
    "preset_name_tt": "저장하거나 덮어쓸 프리셋의 이름",

    "remove_preset": "제거",
    "remove_preset_tt": "이 프리셋을 제거",

    "cancel_action": "취소",

    "remove_preset_confirm": "제거",
    "remove_preset_confirm_tt": "이 프리셋을 제거할 것을 확인",

    "rename_preset": "이름 변경",
    "rename_preset_tt": "이 프리셋의 이름 변경",

    "add_preset": "추가",
    "add_preset_tt": "새 프리셋 추가, 또는 이름이 이미 존재하면 프리셋을 덮어쓰기",

    "overwrite_preset": "덮어쓰기",
    "overwrite_preset_tt": "이 프리셋을 덮어쓰기",

    "overwrite_preset_confirm": "덮어쓰기",
    "overwrite_preset_confirm_tt": "이 프리셋을 대체하고 덮어쓸 것을 확인",

    "save_preset": "저장",
    "save_preset_tt": "현재 속성을 프리셋으로 저장",

    "import_preset": "시드 파일 가져오기...",
    "import_preset_tt":
        "프리셋은 .seed.json 파일에 저장되어 다른 사람과 공유할 수 있습니다 - "
        "하나를 가져와 프리셋 목록에 추가하세요.",

    # Simulate
    "simulation_scale":
        "크기",
    "simulation_scale_tt":
        "다른 가지 크기에 대한 프리셋을 조절하세요. "
        "평균 가지는 1~2년의 성장을 포함하고 약 30cm 길이입니다. "
        "프리셋은 이 크기에 맞춰 설계되었습니다. 하지만 가지 모델은 단일 잎에서부터 몇 년의 성장에 이르기까지 원하는 크기가 될 수 있습니다. "
        "다른 크기의 가지에 맞추는 방법은 단순히 가지 모델의 크기를 확대 또는 축소하면서 원래의 실제 크기를 유지하는 것입니다.",

    "simulation_flushes": "플러시",
    "simulation_flushes_tt":
        "성장할 년수를 설정하세요. "
        "나무의 성장을 작고 상호 작용 가능한 단계로 시뮬레이션하세요. "
        "각 단계 후에 가지치기를 하거나 파라미터를 조정하여 나무를 유도할 수 있습니다.",

    "simulate": "성장",
    "simulate_tt":
        "나무의 자연스러운 성장을 시뮬레이션하세요.",

    "restart": "다시 시작",
    "restart_tt":
        "나무의 특성을 조정하려면 실험이 필요합니다. "
        "성장, 조정, 다시 시작, 반복... 나무를 키우는 방법입니다. "
        "더 많은 옵션을 보려면 더블 클릭하세요.",

    "manual_prune": "가지치기",
    "manual_prune_tt":
        "가지를 제거하거나 단축하기 위해 절단선을 그리세요.",

    "zoom": "확대",
    "zoom_tt": "나무 주변을 돌아다니려면 더블 클릭하세요.",

    # Favor
    "favor_end": "끝",
    "favor_end_tt":
        "Favor End는 가지 끝에 새로운 측면 가지보다 먼저 시작할 수 있는 기회를 줍니다. "
        "처음에는 더 짧고 활력이 떨어지는 측면 가지를 만들지만, 선두 출발이 항상 승리를 보장하는 것은 아닙니다. "
        "Favor Bright가 나타나고 가장 뛰어난 성과를 거두는 쪽의 확률을 높여 "
        "짧은 측면 가지가 따라잡거나 새로운 선두 가지로 나아갈 수 있게 합니다. "
        "Favor Bright와 Favor End는 나무의 가장 중요한 특성 두 가지입니다. "
        "이 두 요소가 함께 작용하여 다양한 모양과 성격을 만들어냅니다.",

    "favor_bright": "밝음",
    "favor_bright_tt":
        "나무의 가지를 수천 개의 개별 식물로 상상해보세요. "
        "밝은 것들은 활력 넘치게 성장하고, 그늘진 것들은 죽습니다 - 이것이 Favor Bright의 극치입니다. "
        "이제 가지를 연결하여 식물들이 이익을 공유할 수 있는 방법을 제공하세요. "
        "당분이 자유롭게 흐르고 빛이 충분할 때, "
        "그늘진 식물들도 성장하고 새로운 빛을 찾는데 필요한 지원을 받을 수 있습니다.",

    "favor_end_reduce": "줄이기",
    "favor_end_reduce_tt":
        "가지가 수직으로 자라는 각도에서 Favor End의 영향을 줄입니다.",

    "favor_rising": "상승",
    "favor_rising_tt":
        "위로 자라는 가지를 아래로 매달린 가지보다 우선시합니다. "
        "상승하는 가지를 높이 올려 탑처럼 솟아오르는 나무를 얻으세요. "
        "값이 1일 경우 수평 가지의 활력을 0으로 줄입니다.",

    # Auto-prune tool
    "panel_auto_prune": "자동 가지치기",

    "auto_prune_enabled": "자동 가지치기",
    "auto_prune_enabled_tt":
        "나무 기반부를 정리하는 측면 가지의 자동, 연간 가지치기입니다. "
        "이를 통해 명확한 전망을 제공하고 사람과 교통이 자유롭게 통과할 수 있습니다. "
        "지면 서리로 인해 손상된 낮게 매달린 가지를 떨어뜨리고 사료를 찾는 동물들이 먹은 가지를 잃습니다. "
        "이 가지치기는 매년 자동으로 수행됩니다.",

    "auto_prune_low": "낮게",
    "auto_prune_low_tt":
        "자동 가지치기는 나무 기반부를 정리하기 위해 낮게 자라는 측면 가지를 매년 자르는 것입니다. 이 가지치기는 나무가 높이 자라면서 점차 발생하며, "
        "나무를 건강하게 유지하기 위해 항상 나무 높이의 1/3까지만 가지치기를 합니다.",

    "auto_prune_keep_thick": "두껍게 유지",
    "auto_prune_keep_thick_tt":
        "더 얇은 가지만 자르고 두꺼운 가지는 유지하세요. "
        "이렇게 하면 나무가 몇 개의 큰 주요 가지를 자라게 할 수 있어 나무가 더 자연스러운 모습이 됩니다 - "
        "공원과 같이 더 많은 공간이 있는 나무를 가지치기할 때 조경가들이 목표로 하는 모습입니다. "
        "이것은 자연에서도 발생하는데, 포식 동물들이 새로운 맛있는 가지를 선호하고 두꺼운 가지는 그대로 두기 때문입니다.",

    "auto_prune_dangling": "매달림",
    "auto_prune_dangling_tt":
    "자동 가지치기 높이 바로 위에 있는 가지는 측면으로 계속 자라고 질량이 증가함에 따라 구부러집니다. "
    "이러한 매달린 가지는 슬픈 버드나무처럼 자라도록 내버려두거나, 설정된 높이로 다시 자를 수 있습니다.",

    # Drop
    "drop_shaded": "그늘진",
    "drop_shaded_tt":
        "그늘진 가지를 떨어뜨립니다. "
        "나무는 매년 모든 방향으로 수많은 새로운 가지를 자라게 합니다. "
        "이 민감한 가지들은 새로운 공간을 탐색하며 빛을 찾습니다. "
        "나무는 가장 많은 빛을 받는 가지에 에너지를 투자하고, 많은 그늘진 가지를 떨어뜨릴 것입니다. "
        "이 값을 줄이면 더 많은 가지를 유지하고 더 조밀한 나무를 자라게 할 수 있고, 높이면 점점 더 밝은 가지를 떨어뜨려 투명하고 열린 나무를 자라게 할 수 있습니다.",

    "drop_obsolete": "쓸모없는",
    "drop_obsolete_tt":
        "나무가 자라면서 낮은 가지들이 그늘지고 작은 가지들이 떨어집니다. "
        "오래된 주요 가지는 줄어든 잎을 지탱하는 것보다 두꺼워질 필요가 없습니다. "
        "이 과다한 나무를 지탱할 수 없게 되면 가지는 결국 쓸모없어지고 썩어 떨어집니다. "
        "이것은 무거운 가지치기 후에도 발생합니다.",

    "drop_decay": "머무르다",
    "drop_decay_tt":
        "나무에 죽은 가지를 남겨두고 시간이 지남에 따라 자연스럽게 썩어 떨어지게 합니다. "
        "특히 침엽수의 아랫부분 줄기는 죽은 가지가 풍부합니다.",

    "drop_weak": "약한",
    "drop_weak_tt":
    "'Favor' 패널에서 가지의 성장 활력이 결정됩니다. "
    "매우 활력이 넘치는 가지는 나무를 새로운 높이로 자라게 하는 데 사용됩니다. "
    "약한 가지는 길이 성장이 멈추며 - 일부는 거절되고 다른 일부는 꽃과 과일을 형성하기 위해 재활용됩니다. "
    "측면 가지들은 여전히 성장을 이어갈 수 있습니다.",

    # Add
    "add_side_branches": "새싹",
    "add_side_branches_tt":
        "노드당 새싹의 수는 가지의 기하학적 배열에 직접적인 영향을 미치며, 교차, 대생, "
        "윤생 패턴은 각각 하나, 둘, 그리고 셋에서 여섯 개의 새싹에 해당합니다. "
        "성장 활력과 확률이 함께 이러한 새싹 중 얼마나 많이 실제로 새 가지로 발달할지 결정합니다.",

    "add_chance": "확률",
    "add_chance_tt":
        "어린 노드가 새 가지를 생성할 확률입니다. "
        "모든 덩굴이 열리고 새 가지를 자라게 할 수 있는 것은 아닙니다. "
        "일부는 서리나 벌레에 의해 손상되고, 다른 일부는 Favor End로 인해 억제됩니다.",

    "add_chance_reduce": "감소",
    "add_chance_reduce_tt":
        "적극성이 떨어지는 가지에 측면 가지를 추가하는 확률을 줄입니다. "
        "측면 가지를 덜 추가하면 이러한 가지들의 두께가 덜 쌓입니다. "
        "결국 낮은 그늘이 드리운 가지들은 땅으로 굴러가게 됩니다.",

    "add_bud_life": "덩굴 생명",
    "add_bud_life_tt":
        "대부분의 종에서 덩굴은 몇 년 동안만 살아남습니다. "
        "이 연령까지의 덩굴은 새로운 가지를 자라게 하는 데 적합합니다. "
        "다른 종에서는 거의 모든 덩굴이 열리고 주로 매우 짧은 가지가 형성되는데, 이는 원추 독점에 의해 제한됩니다. "
        "대부분의 이 가지들은 곧 사라지고, 소수의 가지들은 억제를 벗어나 새로운 가지로 자라납니다.",

    "add_only_on_end": "끝에서만",
    "add_only_on_end_tt":
        "새 가지를 끝 노드에만 추가합니다. "
        "소나무와 같은 나무들은 호르몬으로 측면 성장을 억제합니다. "
        "실제로 이는 끝 근처에 있는 노드만이 호르몬으로부터 자유롭고 새로운 가지를 형성할 수 있다는 것을 의미합니다.",

    "add_fork": "갈래",
    "add_fork_tt":
        "가지가 특히 강하고 활력 있게 자라면 끝 부분 가까이에서 끝 덩굴을 압도할 수 있는 몇 개의 덩굴이 발달할 수 있습니다. "
        "그런 다음 가지가 여러 개의 같은 활력 있는 가지로 나뉩니다. "
        "가운데에 우세한 가지가 없어 그들을 옆으로 밀어내지 못하면, 갈래진 가지들은 정상 각도의 절반에서 자라납니다. "
        "명확한 단일 줄기를 형성하는 대신, 갈래진 나무는 주요 가지들의 확산 구조를 만들어냅니다.",

    "add_regenerate": "재생",
    "add_regenerate_tt":
        "강한 가지치기나 자연 손상으로 인해 가지가 더 멀리 자라면 재생 가지가 형성됩니다. "
        "지지할 수 있는 잎이 적어지면서 남은 나무에서 발생하는 에너지는 나무를 수리하고 공백을 메우기 위해 재생 가지를 생성합니다. "
        "모든 나무가 재생 가지를 자라게 할 수 있는 것은 아닌데, 대부분의 침엽수와 같은 종이 그렇습니다. "
        "이 때문에 이러한 종은 가지치기에 잘 반응하지 않습니다.",

    "add_horizontal": "수평",
    "add_horizontal_tt":
        "덩굴에 대한 플라지오토로피즘입니다. "
        "피엽 배열 각도를 수평 방향으로 돌립니다.",

    "add_angle": "각도",
    "add_angle_tt":
        "기존 가지와 새로 추가된 측면 가지 사이의 각도입니다.",

    "add_up": "위로",
    "add_up_tt":
        "새로운 측면 가지가 위쪽 방향으로 시작합니다. 대신 아래로 자라게 하려면 음수 값을 사용하세요.",

    "add_twist": "비틀기",
    "add_twist_tt":
        "연속적인 노드를 비틀어주세요. "
        "말발굽나무와 같은 종은 가지의 길이를 따라 매우 뚜렷한 비틀림을 가지고 있어, "
        "나무 기둥을 따라 둥근 무늬가 돌아올라가는 것을 확실히 볼 수 있습니다. "
        "눈에 띄는 시각적 품질 외에도, 비틀림은 덩굴의 피엽 회전에도 기여합니다. "
        "이것은 맞은편 가지가 있는 나무의 가지 분포를 개선합니다.",

    "add_planar": "평면",
    "add_planar_tt": "수평 회전과 비슷하지만, 이제 새로운 가지가 성장 방향에 평면으로 돋아납니다.",

    # 성장
    "grow_length": "길이",
    "grow_length_tt":
        "활력 있는 가지는 각 플러시와 함께 이 길이만큼 성장합니다. "
        "보다 약한 가지는 더 짧게 성장할 것입니다.",

    "grow_nodes": "노드",
    "grow_nodes_tt":
        "가지가 매년 성장할 수 있는 최대 노드 수입니다. "
        "활력이 떨어지는 가지는 노드가 더 적게 성장합니다.",

    # 회전
    "turn_up": "위로",
    "turn_up_tt":
        "부정적인 중력 트로피즘. 새로운 성장을 중력에서 멀리 위로 돌려라. "
        "대신 아래로 자라게 하려면 음수 값을 사용하세요.",

    "turn_up_in_shade": "그늘에서 위로",
    "turn_up_in_shade_tt": "그늘진 성장을 중력에서 멀리 위로 돌려라. 대신 아래로 자라게 하려면 음수 값을 사용하세요.",

    "turn_to_light": "빛으로",
    "turn_to_light_tt":
        "광합성. "
        "새로운 성장을 가장 밝은 방향으로 돌립니다. "
        "이 효과는 식물이 창문 쪽으로 자라게 하는 집안의 식물에 나타납니다. "
        "나무에서는 이 효과가 가지의 분포를 개선합니다.",

    "turn_to_horizon": "수평선으로",
    "turn_to_horizon_tt":
        "플라지오토 피즘. "
        "가지가 그늘이 드리워진 상태에서 새로운 성장을 수평면 쪽으로 돌립니다.",

    "turn_random": "무작위",
    "turn_random_tt":
        "가지는 빛이나 중력에 의해 인도되지 않는 임의의 방향으로 움직일 수 있습니다.",

    # 상호작용
    "react_enabled": "반응",
    "react_enabled_tt":
        "메시 객체를 사용하여 새로운 성장을 끌어당기거나, 방향을 바꾸거나, 멈추게 할 수 있습니다. "
        "건물이 그늘을 드리우게 하거나, 독창적인 방법으로 모양 안에 나무를 키울 수 있습니다.",

    "react_block_object": "블록",
    "react_block_object_tt":
        "이 객체와 충돌한 후 성장을 중단합니다.",

    "react_shade_object": "그늘",
    "react_shade_object_tt":
        "이 객체는 건물이나 바위 형태와 같이 빛을 차단합니다. "
        "나무가 어려운 조건에 어떻게 반응하는지 그리고 어떻게 빛을 향해 성장하는지 관찰하세요.",

    "react_deflect_object": "방향 변경",
    "react_deflect_object_tt": "이 객체를 피하세요.",

    "react_attract_object": "유인",
    "react_attract_object_tt":
        "이 객체를 향해 성장하세요. "
        "가지는 이 객체를 통해 자유롭게 성장할 수 있습니다.",

    "react_vigor_object": "활력",
    "react_vigor_object_tt":
        "새로운 성장의 활력을 제어하는 객체를 선택하세요.",

    "react_force": "힘",
    "react_force_tt":
        "물체가 나무에 가하는 힘의 크기입니다.",

    "react_falloff": "감소",
    "react_falloff_tt":
        "효과는 물체에 가까울수록 강하며, 물체와의 거리에 지수적으로 감소합니다.",

    "thicken_tips": "끝",
    "thicken_tips_tt":
        "활력있는 가지의 성장 끝부분의 두께입니다.",

    "thicken_tips_reduce": "줄이기",
    "thicken_tips_reduce_tt":
        "활력이 떨어지는 가지의 성장 끝부분의 두께를 줄입니다. "
        "더 얇은 성장은 더 유연하며, 나무의 형태에 크게 영향을 줍니다. "
        "이것은 특히 측면 가지의 활력을 억제하는 굴러지는 침엽수에 중요합니다.",

    "thicken_join": "결합",
    "thicken_join_tt":
        "두께는 가지의 끝부터 시작되며, 두 개 이상의 가지가 연결될 때마다 "
        "그들의 단면들이 합쳐져 강하고 두꺼운 가지를 만듭니다. "
        "이 과정은 나무 기부터 계속됩니다. "
        "두께의 성장 속도를 달리하면 나무의 모양이 크게 달라집니다. "
        "추가된 두께는 가지를 강화하고 구부러짐을 줄입니다.",

    "thicken_base_scale": "스케일",
    "thicken_base_scale_tt":
        "나무 기반부의 두께를 증가시킵니다.",

    "thicken_base_shape": "형태",
    "thicken_base_shape_tt":
        "뿌리 스케일의 형태를 조절하여 줄기에 들어갑니다.",

    "thicken_base_buttress": "지주근",
    "thicken_base_buttress_tt":
        "뿌리 돌출부와 기초 스케일을 곱합니다. "
        "지주근은 주로 열대 지역의 나무에서 발견되는 기반부의 돌출입니다.",

    "root_distribution": "분포",
    "root_distribution_tt":
        "줄기 전체에 걸친 뿌리 스케일 효과의 범위입니다.",

    "thicken_deadwood": "죽은 나무",
    "thicken_deadwood_tt":
        "가지가 떨어지거나 잘려 날 때, 나무는 상처를 부분적으로 치유하지만, "
        "핵심의 일부는 죽게 됩니다. 나무는 이에 대해 새로운 성장에 더 많은 두께를 "
        "더함으로써 보상합니다. 시간이 지남에 따라 이 과정은 더 두꺼운 줄기를 만들어냅니다.",

    # Bend
    "bend_mass": "질량",
    "bend_mass_tt":
        "가지 무게로 인한 구부러짐 정도. "
        "각 가지가 얼마나 구부러지는지는 그 질량과 두께에 따라 다릅니다. "
        "두꺼운 가지는 무게가 더 나갑니다만, 증가된 단면적으로 인해 중력과 싸움에서 기하급수적으로 강해집니다."
        "가지의 구부러짐은 특히 늙어갈수록 나무의 모양에 중요한 영향을 줍니다. ",

    "bend_twig_mass": "가지 끝 질량",
    "bend_twig_mass_tt":
        "각 가지 끝에 부착된 질량으로, 나무 가지, 잎, 그리고 과일을 포함합니다. "
        "나무는 이를 상쇄하기 위해 새로운 성장을 위로 하려고 합니다. "
        "아래로 구부러지는 것과 위로 자라는 것 사이의 상호 작용은 fastigiate 또는 울창한 나무 캐릭터를 형성하는데 중요한 역할을 합니다.",

    "bend_twig_mass_solidify": "굳히기",
    "bend_twig_mass_solidify_tt":
        "가지 끝에 당기는 무게로 인한 구부러짐을 고정시킵니다. "
        "가지 끝의 질량은 계절에 따라 다르며, 무거운 봄꽃, "
        "크고 두툼한 잎과 과일이 모두 가지를 아래로 당깁니다. "
        "하지만 가지가 딱딱해지는 시기가 되면 이미 대부분의 질량이 떨어져 있을 수 있습니다.",

    "bend_reaction": "반응",
    "bend_reaction_tt":
        "반응 나무는 빠르게 두꺼워지는 가지가 시간이 지남에 따라 적극적으로 다시 위로 휘어지도록 합니다. "
        "가지가 수직 성장 방향에서 더 멀어질수록 효과가 강해집니다. "
        "경사진 나무는 수직으로 돌아갈 수 있고, 활력있는 측가지가 새로운 리더로 빠르게 성장할 수 있습니다.",

    # Shade
    "shade_area": "잎 면적",
    "shade_area_tt":
        "각 가지 끝에 결합된 잎의 면적, dm² (10cm x 10cm) 단위로 표시됩니다.",

    "shade_area_reduce": "줄이기",
    "shade_area_reduce_tt":
        "활력이 떨어지는 가지의 잎 면적을 줄입니다.",

    "shade_area_depth": "깊이",
    "shade_area_depth_tt":
        "그늘 주조부의 옆면을 들어 올려 모양에 더 깊이를 줍니다. "
        "이렇게 하면 나무의 옆면에서 더 많은 그늘이 발생하고 전반적으로 더 많은 그늘이 발생합니다. "
        "그늘 미리보기를 사용하여 효과를 확인하세요.",

    "tweak": "그늘 조정",
    "tweak_tt": "그늘 매개 변수를 시각적으로 조정합니다.",

    "shade_leaf_sides": "옆면",
    "shade_leaf_sides_tt":
        "그림자를 드리우는 잎 면적을 가지의 옆면에도 분산시킵니다. "
        "대부분의 나무는 가지 끝의 잎만으로도 잘 모사될 수 있으며, 이러한 작은 추상화가 잘 작동합니다. "
        "그러나 울창한 가지를 가진 나무에서는 옆쪽 가지가 필요합니다. 이렇게 하면 더 작은 잎 면적이 필요하다는 점에 유의하세요. "
        "더 많은 가지가 배치되기 때문입니다.",

    # Build
    "rebuild": "재구축",
    "rebuild_tt":
        "다각형 축소, 속성, 그리고 가지 분포를 업데이트하기 위해 나무의 3D 모델을 재구축합니다.",

    "build_resolution": "해상도",
    "build_resolution_tt":
        "나무의 기초에서 가장 두꺼운 부분에 있는 정점의 수입니다.",

    "build_resolution_reduce": "줄이기",
    "build_resolution_reduce_tt":
        "가늘어진 가지에 대한 다각형을 줄입니다. "
        "나무의 대부분의 다각형은 수천 개의 어린 가지에 있습니다. "
        "이러한 얇은 가지는 시각적 품질을 잃지 않고 다각형을 줄일 수 있습니다.",

    "smooth": "부드럽게",
    "smooth_tt":
        "날카로운 모서리의 각도를 줄여 더 부드럽게 구부러지는 가지를 만듭니다.",

    "texture_bark": "나무껍질",
    "texture_bark_tt": "텍스처를 선택하세요",

    "texture_repeat": "반복",
    "texture_repeat_tt":
        "나무 기초의 둘레를 따라 나무껍질 텍스처를 반복하는 횟수로, 가늘어진 가지에서 자동으로 줄어듭니다.",

    # Twigs
    "twig_menu": "작은 가지",
    "twig_menu_tt":
        "나무에 작은 가지를 추가하려면 작은 가지 세트를 선택하세요. "
        "이 메뉴에는 작은 가지 폴더에서 찾을 수 있는 모든 작은 가지가 나열됩니다 - Grove 사용자 환경 설정에서 폴더를 선택할 수 있습니다. "
        "또는 현재 장면의 객체를 선택할 수도 있습니다.",

    "twig_pick_objects": "장면 객체",
    "twig_pick_objects_tt": "장면의 3D 객체를 선택하세요.",

    "twig_pick_collections": "컬렉션",
    "twig_pick_collections_tt": "현재 파일에서 작은 가지 객체의 컬렉션을 선택하세요.",

    "twig_no_twigs": "작은 가지 없음",
    "twig_no_twigs_tt": "작은 가지가 없습니다.",

    "twig_object_end": "끝",
    "twig_object_end_tt":
        "가지 끝에 분배할 작은 가지 객체. "
        "끝 작은 가지는 새로운 성장으로 나뭇잎과 때때로 꽃과 나중에 열매가 있습니다. "
        "끝 작은 가지는 기존 가지에 연장선이며 종종 옆 작은 가지보다 훨씬 강하고 길다.",

    "twig_object_side": "옆",
    "twig_object_side_tt":
        "가지의 옆면에 분배할 작은 가지 객체. "
        "옆 작은 가지는 기존 가지의 옆면에서 발달하는 새로운 가지입니다. "
        "나뭇잎과 때때로 꽃과 나중에 열매를 지지합니다. "
        "옆 작은 가지는 주 가지에 의해 만들어진 호르몬 억제로 인해 종종 끝 작은 가지보다 짧습니다. "
        "가장 강한 것들만 결국 완전한 새 가지로 자랄 것입니다.",

    "twig_object_upward": "상승",
    "twig_object_upward_tt":
        "급격하게 위로 자라는 작은 가지 모델. "
        "상승하는 작은 가지는 종종 더 길고, 나뭇잎이 모든 방향으로 휘감기도 합니다. "
        "이 작은 가지는 선택 사항이며; 선택하지 않으면 대신 끝 작은 가지를 사용합니다.",

    "twig_object_dead": "죽은 가지",
    "twig_object_dead_tt":
        "약하거나 죽은 작은 가지의 모델. "
        "이 작은 가지는 선택 사항이며, 나무의 약한 부분에 세부 사항을 추가하는 데 사용할 수 있습니다.",

    "twig_wither": "시들다",
    "twig_wither_tt":
        "죽은 작은 가지가 나무에서 얼마나 오래 (‘생명’ 이후 몇 년 동안) 남아 시들게 되는지를 나타내는 숫자입니다. "
        "효과를 확인하려면 다시 빌드하세요.",

    "twig_density": "밀도",
    "twig_density_tt":
        "더 많거나 덜 많은 옆 작은 가지를 추가하여 나무의 나뭇잎 밀도를 조절하세요. "
        "이것은 죽은 작은 가지의 밀도에도 영향을 줍니다. "
        "끝 작은 가지는 영향을 받지 않고 항상 모든 살아있는 가지 끝에 추가됩니다.",

    "twig_view_detail": "뷰 세부 정보",
    "twig_view_detail_tt":
        "뷰포트 성능을 향상시키기 위해, 각 작은 가지 모델에 'Decimate' 수정자를 추가하여 디스플레이 해상도가 줄어듭니다."
        "뷰포트는 수정된 저해상도 모델을 사용하고, 렌더 엔진은 원본을 사용합니다.",

    "twig_hide": "",
    "twig_hide_tt": "가지를 명확하게 볼 수 있도록 뷰포트에서 작은 가지를 숨기고 뷰포트 성능을 향상시키세요.",

    "twig_longevity": "장수",
    "twig_longevity_tt":
        "옆 작은 가지는 올해 자란 새로운 노드의 모든 가지 끝 부근에 나타납니다. "
        "장수는 점점 더 오래된 노드에서 작은 가지를 여러 년 동안 견디도록 만듭니다. "
        "변경 사항을 표시하려면 다시 빌드해야 합니다.",

    "twig_side_on_tips": "끝부분에 작은 가지",
    "twig_side_on_tips_tt":
        "끝 작은 가지 옆에 모든 가지 끝에도 옆 작은 가지를 추가하세요. "
        "효과를 확인하려면 나무를 다시 빌드하세요.",


    # Preferences
    "save_preferences": "환경 설정 저장",
    "save_preferences_tt": "이 설정을 기억하기 위해 환경 설정을 저장하세요.",

    "language": "언어",
    "language_tt": "인터페이스와 툴팁에 사용할 언어",

    "use_adaptive_units": "적응형 단위 사용",
    "use_adaptive_units_tt":
        "Grove는 일부 파라미터에 대해 매우 작은 거리를 나타내는 단위를 사용합니다. "
        "적응형 단위가 활성화되면 0.001m은 1mm로 표시됩니다.",

    "grove": "그로브",

    "label_direction": "시작 방향",

    "label_layers": "속성",

    "add_new_grove": "그로브 추가",
    "add_new_grove_tt": "새 그로브 컬렉션을 추가하세요.",

    "select_a_grove_collection": "트리가 있는 콜렉션 선택",

    "select_linked_branches_tt": "현재 선택 항목을 전체 가지와 옆 가지로 확장합니다.",
    "select_linked_branches": "연결된 가지 선택",

    "select_thicker": "두꺼운 것 선택",
    "select_thicker_tt": "'두께' 속성을 사용하여 더 두꺼운 가지 노드에 속하는 기하학을 선택합니다.",
    "select_thicker_threshold": "임계값",

    "show_dead_preview": "죽은 것 표시",

    "disable_outline": "윤곽선 비활성화",
    "disable_outline_tt":
        "클릭하여 나무의 정확한 표현과 트윅하는 동안 더 나은 시각적 피드백을 위해 윤곽선 쉐이딩을 비활성화하세요. "
        "윤곽선 쉐이딩으로 가지가 실제보다 훨씬 두껍게 보입니다.",

    "set_background": "배경 밝게하기",
    "set_background_tt":
        "뷰포트 배경을 밝게 하고 중간 회색으로 설정하려면 클릭하세요. "
        "개선된 대비로 인해 나무 가지가 훨씬 더 쉽게 볼 수 있습니다.",


    # Record
    "record_enabled": "녹화",
    "record_enabled_tt":
        "'Record'라는 전용 컬렉션에 객체 시퀀스로 성장을 기록합니다. "
        "각 단계는 시간이 짧게 보이도록 키 프레임화됩니다. "
        "이러한 객체들의 시퀀스가 성장 애니메이션을 형성합니다.",

    "record_start": "시작 프레임",
    "record_start_tt":
        "이 프레임에서 시작하도록 애니메이션을 시간을 앞당겨 설정하세요.",

    "record_interval": "간격",
    "record_interval_tt":
        "각 해는 나무의 초기 봄 모양에서 완전히 자란 여름 모양까지 부드러운 보간입니다. "
        "이 보간에 대한 프레임 수를 정의하고 이에 따라 성장 속도를 설정합니다. "
        "이 값은 언제든지 조정할 수 있으며, 애니메이션은 즉시 업데이트됩니다.",

    "regrow": "재성장",
    "regrow_tt":
        "현재 굵게 나온 수의 개수까지 다시 시작하여 빠르게 새로운 나무를 성장시키세요. "
        "나무를 자르는 기회를 건너뛰고 한 번에 성장시키세요.",

    "placeholder_delay": "지연",
    "placeholder_delay_tt":
        "성장을 시작하기 전에 기다릴 연수를 설정하세요.",

    "panel_build_base": "기초",

    "add_tree": "나무 추가",
    "add_tree_tt":
        "성장을 시작할 빈 객체를 추가합니다. "
        "객체를 이동, 회전, 복제 또는 삭제하여 각기 다른 위치와 각도에서 나무 그룹을 성장시키세요.",

    "old_release_warning_line_1": "이전 버전에서 성장한 나무.",
    "old_release_warning_line_2": "많은 것이 변경되었습니다.",
    "old_release_warning_line_3": "이전 버전을 사용하여 수정하세요.",

    "grow_together": "함께 성장하기",
    "grow_together_tt_short":
        "모든 그루브 컬렉션을 하나로 함께 성장시킵니다.\n"
        "나무 종류를 섞고, 빛을 향해 경쟁하게 만듭니다.",
    "grow_together_tt":
        "서로 다른 나무 종을 섞을 수 있도록 모든 별도의 그루브 컬렉션을 하나로 함께 성장시킵니다."
        "빛을 향해 경쟁하도록 결합된 그늘과 광성장 계산을 사용합니다.",

    "restart_all": "모두 다시 시작",
    "restart_all_tt": "모든 그루브 컬렉션을 다시 시작합니다.",

    "draw": "그리기",
    "draw_tt": "경로를 따라 새로운 가지를 성장시킵니다.",

    "prune_status_draw_lines": "그리기",


    # Bend tool
    "manual_bend": "굽히기",
    "manual_bend_tt":
        "금속 와이어로 나무 가지를 구부리는 분재 기술에서 영감을 받은 도구지만, 훨씬 더 유연하게, "
        "가장 두꺼운 가지조차도 굽힐 수 있으며, 성장한 나무조차도 스타일링할 수 있습니다.",

    "bend_status_select_node": "노드 선택",

    "bend_tool_distance": "거리",
    "bend_tool_distance_tt": "",

    "bend_tool_bend_button": "굽히기",
    "bend_tool_bend_button_tt": "Space",

    "close_button": "",
    "close_button_tt": "닫기",

    "close": "닫기",

    "turntable": "",
    "turntable_tt": "보기",

    "bend_tool_curve": "곡선",
    "bend_tool_curve_tt": "굽힘의 모양",
    "bend_tool_curve_simple": "단순",
    "bend_tool_curve_flexible": "유연",
    "bend_tool_curve_s_curve": "S-곡선",


    # Wind
    "wind_vector": "바람",
    "wind_vector_tt": "속도와 방향",
    "wind_turbulence": "난류",
    "wind_turbulence_tt": "가지를 들어올리고 바람에 나뭇가지를 춤추게 합니다.",

    "wind_shapes": "모양 키",
    "wind_shapes_tt":
        "모양 키의 수는 바람 애니메이션의 길이를 정의하며, 이후에 자동으로 반복됩니다. "
        "각 모양은 2 프레임 간격으로 키 프레임이 지정되고, 하나의 모양에서 다음 모양으로 부드럽게 보간됩니다. ",

    "label_animating_wind": "바람 애니메이션 중...",
    "label_stop": "중지",

    "wind_breeze": "산들바람",
    "wind_breeze_tt":
        "산들바람 애니메이션으로 나뭇가지에 생기를 불어넣습니다. "
        "보다 강한 변형을 위해 일반 바람 애니메이션과 결합할 수 있습니다.",

    "calculate_wind": "애니메이션",
    "calculate_wind_tt":
        "바람 애니메이션을 추가합니다. "
        "이것은 시간이 지남에 따라 나무의 가지를 변형시키는 일련의 모양 키를 생성합니다.",

    "grow_tool_growing": "성장 중",
    "grow_tool_growing_tt": "취소하려면 Escape를 누르세요.",
    "grow_tool_building": "메시 구축 중",

    # Plant operator.
    "plant": "식재",
    "plant_tt":
        "나무 그룹을 식재하여 과수원, 담장, 나무 섬 등을 만듭니다. "
        "이 도구는 빈 객체를 생성하며, 자유롭게 이동, 복제 또는 삭제할 수 있습니다.",

    "plant_layout": "레이아웃",
    "plant_layout_tt": "과수원, 플랜테이션, 담장, 반지 또는 자연적인 나무 덩어리를 식재합니다",

    "plant_trees": "나무",
    "plant_trees_tt": "나무 수",

    "plant_space": "간격",
    "plant_space_tt": "나무 사이의 거리",

    "plant_random_shift": "무작위 이동",
    "plant_random_shift_tt": "불규칙한 배치",

    "plant_random_seed": "무작위 시드",
    "plant_random_seed_tt": "무작위 이동을 다양화합니다",

    "plant_delay": "지연",
    "plant_delay_tt": "중심에서 먼 나무들이 나중의 해에 성장을 시작합니다.",

    "plant_ring_radius": "반지름",
    "plant_ring_radius_tt": "반지 중심으로부터의 거리",

    "plant_rows_trees_tt": "행당 나무 수",

    "plant_rows": "행",
    "plant_rows_tt": "행의 수",

    "plant_rows_space": "간격",
    "plant_rows_space_tt": "행 사이의 간격",

    "plant_rows_diagonal": "대각선",
    "plant_rows_diagonal_tt": "다이아몬드 패턴을 얻기 위해 두 번째 행마다 이동",

    "plant_islands_trees_tt": "섬당 평균 나무 수",

    "plant_islands": "섬",
    "plant_islands_tt": "나무 섬의 수",

    "plant_islands_space": "섬 간격",
    "plant_islands_space_tt": "나무 섬 사이의 평균 거리",

    "plant_islands_clearing": "공터",
    "plant_islands_clearing_tt": "중앙의 열린 공간",

    "plant_islands_randomize": "무작위",
    "plant_islands_randomize_tt": "섬당 나무 수를 다양화합니다",

    "plant_layout_clump": "덩어리",
    "plant_layout_rows": "행",
    "plant_layout_ring": "반지",
    "plant_layout_islands": "섬",

    "plant_variation_panel": "변형",
    "plant_diverge": "분기",
    "plant_diverge_tt": "근처의 나무들로부터 떨어져 돌아갑니다.",

    "plant_terrain_panel": "지형",
    "plant_terrain_drop": "낙하",
    "plant_terrain_drop_tt": "나무를 땅에 투사합니다.",

    "plant_terrain_slope": "경사",
    "plant_terrain_slope_tt": "지형의 경사를 회전에 반영합니다.",

    "escape_to_stop": "중지하려면 Escape",

    "replant_grove": "다시 식재",
    "replant_grove_tt": "다시 식재합니다.",

    # Surround tool
    "surround_enabled": "둘러싸기",
    "surround_enabled_tt":
        "나무를 모든 측면에서 그늘에 둘러싸십시오. "
        "이렇게 하면 나무가 더 높게 자라고 하부 가지를 더 많이 잃게 됩니다. "
        "전체 숲을 키우지 않고도 숲에서 발견되는 나무와 유사한 나무를 키울 수 있습니다.",
    "surround_density": "밀도",
    "surround_density_tt":
        "개방된 들판 또는 조밀한 숲이나 그 사이의 어떤 곳에서든 자라십시오.",
    "surround_height": "높이",
    "surround_height_tt":
        "기존 나무나 건물에 사용할 수 있는 고정 높이. "
        "자동 높이를 사용하여 주변이 나무와 함께 자라게 할 수 있습니다.",
    "surround_grow": "성장",
    "surround_grow_tt":
        "매년 자동으로 높이가 증가합니다 - 주변 나무들이 나무와 함께 성장합니다.",
    "surround_distance": "거리",
    "surround_distance_tt": "자라기 위한 공간을 확보합니다.",

    # File tool
    'file': "파일",
    "file_tt": "나중에 사용할 나무를 저장하거나 애플리케이션 간에 나무를 전송하세요.",

    "file_recent": "최근",

    "file_import": "나무 가져오기",
    "file_import_tt": ".grove 파일에서 시뮬레이션을 가져옵니다.",

    "file_export": "나무 내보내기",
    "file_export_tt": "현재 시뮬레이션을 .grove 파일로 내보냅니다.",

    # Roots tool
    "roots": "뿌리",
    "roots_tt":
        "표면 뿌리 생성하기. "
        "뿌리는 보통 땅 아래에서 자라지만, 토양 침식으로 인해 드러날 수 있습니다. "
        "시각적으로 매력적인 표면 뿌리는 나무를 땅에 고정시킵니다.",
    
    "roots_roots_panel": "뿌리",
    "roots_number": "개수",
    "roots_number_tt": "주요 뿌리의 개수",
    "roots_nodes": "노드",
    "roots_nodes_tt": "각 뿌리의 노드 개수",
    "roots_length": "길이",
    "roots_length_tt": "두 노드 사이의 길이.",
    "roots_climb": "오르기",
    "roots_climb_tt": "줄기를 따라 뿌리가 올라가서 부드러운 혼합을 만듭니다.",
    "roots_turn_down": "아래로 자라기",
    "roots_turn_down_tt": "",

    "roots_branches_panel": "측면 뿌리",
    "roots_branches_panel_tt": "",
    "roots_generations": "세대",
    "roots_generations_tt": "뿌리 시스템을 더욱 자세히 확장하기 위해 성장의 추가 세대를 추가합니다.",
    "roots_density": "밀도",
    "roots_density_tt":
        "측면 뿌리가 자라는 확률입니다. 밀도를 더욱 높이려면, "
        "노드 수를 늘리고 노드 간 길이를 줄입니다.",
    "roots_add_angle": "각도",
    "roots_add_angle_tt": "주요 뿌리로부터의 각도.",
    "roots_add_down": "아래로 추가",
    "roots_add_down_tt": "",

    "roots_variation_panel": "무작위",
    "roots_random_heading": "방향",
    "roots_random_heading_tt": "땅 위를 기어가다.",
    "roots_random_pitch": "피치",
    "roots_random_pitch_tt": "성장하는 동안 위아래로 돌립니다.",
    "roots_random_seed": "시드",
    "roots_random_seed_tt": "",

    "roots_thickness_panel": "두께",
    "roots_thickness": "두께",
    "roots_thickness_tt": "주요 뿌리의 평균 두께.",
    "roots_thickness_reduce": "줄이기",
    "roots_thickness_reduce_tt": "",
    "roots_thickness_random": "무작위",
    "roots_thickness_random_tt": "",

    "roots_terrain_panel": "지형",
    "roots_terrain_panel_tt": "",
    "roots_drop": "내리기",
    "roots_drop_tt": "",

    "restart_single_tree": "단일 나무",
    "restart_single_tree_tt":
        "플레이스홀더를 제거하고 원점에 단일 나무를 심습니다.",

    "restart_revert": "처음부터 시작",
    "restart_revert_tt":
        "모든 것을 기본값으로 초기화하고, 활성 프리셋을 다시 불러오고, 단일 나무로 다시 시작합니다.",

    "operator_turntable": "보기",
    "operator_turntable_tt":
        "눈 높이에서 나무를 감상하세요 - 나무 주변과 그늘진 곳을 돌아다닙니다.",

    "stake_enabled": "지지대",
    "stake_enabled_tt": "지지대는 줄기를 지탱하여 직선으로 위로 자라게 합니다.",
    "stake_height": "높이",
    "stake_height_tt": "줄기가 직선으로 위로 자라도록 나무를 이 높이까지 지탱합니다.",
    
    "sow_enabled": "파종",
    "sow_enabled_tt": "기존의 오래된 나무 주변에 씨앗을 퍼뜨려 자연스럽게 퍼지는 숲을 시뮬레이션합니다.",
    
    "sow_age": "지연",
    "sow_age_tt": "나무는 씨앗을 생산하기 시작하기 전에 뿌리를 내리고 에너지 양성 상태를 확립하는 데 몇 년이 걸립니다.",
    
    "sow_chance": "확률",
    "sow_chance_tt":
        "매년 각 나무가 성공적인 자손을 만들 확률입니다."
        "실제로는 일부 나무가 매년 수천 개의 씨앗을 만들고, 이 중 수백 개가 발아할 수 있습니다."
        "하지만 거의 없는 씨앗만이 제대로 된 나무로 자랍니다."
        "시뮬레이션을 사용 가능한 속도로 유지하려면 확률을 낮게 유지하세요.",
    
    "sow_distance": "거리",
    "sow_distance_tt": "씨앗은 기존 나무 주변의 거리 내에 퍼집니다.",
    
    "sow_limit": "제한",
    "sow_limit_tt": "최대 나무 수. 시뮬레이션이 원활하게 실행되도록 이 수를 초과하여 새 나무를 추가하지 않습니다.",
    
    "build_skeleton": "스켈레톤 구축",
    "build_skeleton_tt": "본, 본 웨이트 그룹 및 바람 애니메이션을 생성합니다.",
    
    "skeleton": "스켈레톤",
    "skeleton_tt": 
        "본을 사용하여 나무를 애니메이션화할 수 있는 스켈레톤을 생성합니다. "
        "또한 메시 포인트를 해당 본에 연결하는 버텍스 그룹도 추가합니다. "
        "선택적으로, 새 본에 바람 애니메이션을 추가할 수 있습니다.",
    
    "skeleton_panel_bones": "본",
    "skeleton_panel_wind": "바람",
    
    "skeleton_reduce": "감소",
    "skeleton_reduce_tt": "얇은 측면 가지를 건너뛰어 본의 수를 줄입니다.",
    
    "skeleton_bias": "편향",
    "skeleton_bias_tt": "더 많은 본을 위쪽에 추가하려면 증가시키고, 아래쪽에 더 많은 본을 추가하려면 감소시킵니다.",
    
    "skeleton_length": "길이",
    "skeleton_length_tt": "노드를 건너뛰어 더 긴 본을 생성합니다.",
    
    "skeleton_connected": "연결됨",
    "skeleton_connected_tt":
        "블렌더는 떠 있는 본으로부터 계층 구조를 구축할 수 있지만, 일부 다른 프로그램에서는 연결된 본 체인이 필요합니다. "
        "이 연결에는 각 분기점마다 새 본이 필요하며, 이로 인해 본의 수가 증가합니다.",
    
    "add_planar": "평면적",
    "add_planar_tt": "수평 회전과 유사하게, 이제 새로운 가지가 성장 방향에 평면으로 돋아납니다.",
    
    "shade_branches": "가지",
    "shade_branches_tt": "대부분의 그림자는 잎에서 오지만, 일부 나무에서는 가지 형상을 그림자 계산에 포함할 수 있습니다.",
    
    "shade_branches_panel": "가지",
    "shade_leaves_panel": "잎",
    
    # User preferences
    "presets_path": "프리셋 폴더",
    "presets_path_tt":
        "프리셋을 저장하는 폴더를 선택하세요. 이 폴더의 모든 프리셋이 프리셋 선택기에 표시됩니다.",
    
    "use_scientific_names": "학명 사용",
    "use_scientific_names_tt":
        "가능한 경우 작은 가지 종을 학명으로 표시합니다. "
        "비활성화하면 작은 가지 메뉴에 일반 영어 이름이 표시됩니다.",
    
    "shade_alongside": "측면",
    "shade_alongside_tt": "새로 자란 작은 가지 외에도, 소나무와 같은 나무들은 오래된 바늘잎이 가지 옆에 있습니다.",
    
    "shade_alongside_diameter": "직경",
    "shade_alongside_diameter_tt": "가지 옆에 그림자를 드리우는 형상의 직경입니다.",
    
    "build_cutoff_age": "연령 절단",
    "build_cutoff_age_tt":
        "세부 수준은 다각형 수를 크게 줄이기 위해 최근 몇 년간의 성장 구축을 건너뜁니다. "
        "이는 동일한 연수의 성장을 나타내는 더 큰 작은 가지로 보완해야 합니다.",
    
    "build_cutoff_thickness": "두께 절단",
    "build_cutoff_thickness_tt": "이 직경 이하의 노드 구축을 건너뜁니다.",
    
    "build_triangulate": "삼각형화",
    "build_triangulate_tt": "나무의 가지를 구축하는 데 사각형이 아닌 삼각형만 사용합니다.",
    
    "build_blend": "블렌딩",
    "build_blend_tt":
        "한 가지에서 다른 가지로 매끄러운 전환을 만들기 위해 추가 노드를 추가합니다. "
        "이는 더 두꺼운 가지에서 시각적으로 중요하지만, 다각형 수를 크게 줄이기 위해 더 얇은 가지에서는 비활성화할 수 있습니다.",
    
    "build_end_cap": "끝 캡",
    "build_end_cap_tt":
        "가지의 열린 끝을 확장된 점에 연결하는 다각형으로 닫습니다. "
        "작은 가지를 사용하거나 적당한 거리에서 볼 때 캡을 제거하면 다각형 수가 크게 줄어들고 거의 눈에 띄지 않습니다.",
    
    "detail_simplify": "단순화",
    "detail_simplify_tt":
        "방향 변화가 거의 없는 직선 노드를 건너뛰어 가지를 단순화합니다. 이는 다각형 수를 약간 줄입니다.",
    
    "fallback_instructions": "성장 준비하기",
    "fallback_instructions_tt": "시뮬레이션 코어를 설치하려면 http://www.thegrove3d.com/info/install/ 의 지침을 따르세요.",
    
    "trial_end": "지금 구매...",
    "trial_end_tt": "평가판이 만료되었습니다. The Grove가 마음에 드셨다면 라이센스를 구매하여 멋진 나무를 계속 키워주세요."
}
